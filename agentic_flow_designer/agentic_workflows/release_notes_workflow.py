import os
import sys
import threading
import queue
import requests
import subprocess
from typing import Dict, Any, Optional


class EnvironmentError(Exception):
    pass


def validate_env_vars_and_secrets(env_vars, secrets):
    missing = []
    for var in env_vars + secrets:
        if not os.getenv(var):
            missing.append(var)
    if missing:
        raise EnvironmentError(f"Missing required environment variables or secrets: {', '.join(missing)}")


class FetchPRDataAgent:
    """Retrieve pull request data from GitHub."""

    REQUIRED_SECRETS = ["GITHUB_TOKEN"]

    def __init__(self):
        validate_env_vars_and_secrets([], self.REQUIRED_SECRETS)
        self.github_token = os.getenv("GITHUB_TOKEN")

    def fetch_prs(self) -> str:
        # TODO: Adjust repo and filtering criteria as needed
        repo = os.getenv("GITHUB_REPOSITORY", "owner/repo")  # e.g. "owner/repo"
        url = f"https://api.github.com/repos/{repo}/pulls"
        headers = {"Authorization": f"token {self.github_token}", "Accept": "application/vnd.github.v3+json"}
        params = {"state": "closed", "per_page": 100}

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"GitHub API request failed with status {response.status_code}: {response.text}")

        prs = response.json()

        # Filter PRs merged recently (e.g., last release) - here we just take all closed merged PRs
        merged_prs = [pr for pr in prs if pr.get("merged_at")]

        # Compose raw release notes data as JSON string
        import json
        raw_data = json.dumps(merged_prs)
        return raw_data

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        release_notes_raw = self.fetch_prs()
        return {"release_notes": release_notes_raw}


class GenerateReleaseNotesAgent:
    """Create formatted release notes from PR data."""

    def __init__(self):
        # No env vars or secrets required
        pass

    def format_notes(self, raw_pr_data: str) -> str:
        import json
        try:
            prs = json.loads(raw_pr_data)
        except Exception as e:
            raise RuntimeError(f"Failed to parse PR data JSON: {e}")

        # Format release notes in a user-friendly manner
        notes_lines = ["*Release Notes:*\n"]
        for pr in prs:
            number = pr.get("number")
            title = pr.get("title")
            user = pr.get("user", {}).get("login")
            merged_at = pr.get("merged_at")
            notes_lines.append(f"- PR #{number}: {title} (by @{user}, merged {merged_at})")

        formatted_notes = "\n".join(notes_lines)
        return formatted_notes

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        raw_notes = inputs.get("release_notes")
        if raw_notes is None:
            raise ValueError("Input 'release_notes' is required for GenerateReleaseNotesAgent")
        formatted = self.format_notes(raw_notes)
        return {"release_notes": formatted}


class SendToSlackAgent:
    """Send the release notes to a specified Slack channel."""

    REQUIRED_SECRETS = ["SLACK_WEBHOOK_URL"]

    def __init__(self):
        validate_env_vars_and_secrets([], self.REQUIRED_SECRETS)
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    def post_to_slack(self, message: str) -> None:
        payload = {"text": message}
        response = requests.post(self.webhook_url, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Slack webhook failed with status {response.status_code}: {response.text}")

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        message = inputs.get("release_notes")
        if message is None:
            raise ValueError("Input 'release_notes' is required for SendToSlackAgent")
        self.post_to_slack(message)
        return {}


class FinalValidationAgent:
    """Validate the successful sending of release notes to Slack."""

    def __init__(self):
        # No env vars or secrets required
        pass

    def validate_slack_message(self) -> None:
        # TODO: Implement actual validation if possible
        # For now, just log success
        print("Final validation: Release notes sent to Slack successfully.")

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_slack_message()
        return {}


class WorkflowCoordinator:
    """Coordinates execution of agents respecting dependencies."""

    def __init__(self):
        self.agents = {
            "fetch_pr_data": FetchPRDataAgent(),
            "generate_release_notes": GenerateReleaseNotesAgent(),
            "send_to_slack": SendToSlackAgent(),
            "final_validation": FinalValidationAgent(),
        }

        # Define dependencies as per execution_graph
        self.dependencies = {
            "fetch_pr_data": [],
            "generate_release_notes": ["fetch_pr_data"],
            "send_to_slack": ["generate_release_notes"],
            "final_validation": ["send_to_slack"],
        }

        # Store outputs keyed by agent name
        self.outputs: Dict[str, Dict[str, Any]] = {}

    def run_workflow(self, task_context: Optional[Dict[str, Any]] = None) -> None:
        if task_context is None:
            task_context = {}

        # Execution order is linear here, but we implement a DAG executor for extensibility
        executed = set()
        to_execute = set(self.agents.keys())

        # Use a simple queue to manage ready agents
        ready_queue = queue.Queue()

        # Initialize ready queue with agents with no dependencies
        for agent_name, deps in self.dependencies.items():
            if not deps:
                ready_queue.put(agent_name)

        while not ready_queue.empty():
            agent_name = ready_queue.get()
            agent = self.agents[agent_name]

            # Prepare inputs by gathering outputs from dependencies
            inputs = {}
            for dep in self.dependencies[agent_name]:
                dep_outputs = self.outputs.get(dep, {})
                inputs.update(dep_outputs)

            # Merge with task_context for initial inputs
            if agent_name == "fetch_pr_data":
                # fetch_pr_data has no inputs, but can receive context
                inputs.update(task_context)

            try:
                output = agent.run(inputs)
            except EnvironmentError as e:
                print(f"Environment validation error in {agent_name}: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error running agent {agent_name}: {e}", file=sys.stderr)
                sys.exit(1)

            self.outputs[agent_name] = output
            executed.add(agent_name)

            # Enqueue agents that depend on this one if all their dependencies are met
            for next_agent, deps in self.dependencies.items():
                if next_agent not in executed and all(d in executed for d in deps):
                    ready_queue.put(next_agent)


# Entrypoint

def run_workflow(task_context: Dict[str, Any]) -> None:
    """
    Run the release notes automation workflow.

    Args:
        task_context (dict): Optional initial context inputs.

    Raises:
        EnvironmentError: If required environment variables or secrets are missing.
        RuntimeError: If any agent fails during execution.

    Usage:
        Set environment variables GITHUB_TOKEN, SLACK_WEBHOOK_URL, and optionally GITHUB_REPOSITORY.
        Then call run_workflow({}) to execute the workflow.
    """
    coordinator = WorkflowCoordinator()
    coordinator.run_workflow(task_context)


# Guidance:
# - To extend the workflow, add new agent classes and update WorkflowCoordinator dependencies.
# - To execute, ensure environment variables are set, then call run_workflow({}).
# - Customize repository and filtering logic in FetchPRDataAgent as needed.

if __name__ == "__main__":
    # Example execution
    try:
        run_workflow({})
        print("Workflow completed successfully.")
    except Exception as e:
        print(f"Workflow failed: {e}", file=sys.stderr)
        sys.exit(1)
