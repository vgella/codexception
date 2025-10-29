# Agentic Flow Designer Tools

This repository packages an MCP server that lets the Codex CLI delegate complex work to a purpose-built, multi-agent workflow. When Codex detects a task that benefits from deeper coordination, it can call these tools to:

- assess whether delegation is worthwhile,
- plan a division of labor across specialized agents,
- generate production-ready OpenAI Agents SDK code,
- simulate a full run, evaluate the results, and iterate until the solution meets a quality bar.

The server automatically exposes Codex itself plus every endpoint in this suite to the generated agents, so they can keep delegating recursively while respecting any extra tools you provide.

## Repository Layout

- `agentic_flow_designer/server.py` – MCP server that orchestrates planning, code generation, simulation, evaluation, and revision.
- `agentic_flow_designer/manifest.json` – Tool metadata consumed by the Codex CLI.
- `agentic_flow_designer/run_server.sh` – Helper launcher Codex invokes so the server runs with the right working directory and logging.
- `agentic_flow_designer/agentic_workflows/` – Destination folder for generated Agents SDK code (example workflow included).
- `agentic_flow_improvements.txt` – Design goals that shaped the tool behavior.
- `release_notes_workflow.py` – Sample code artifact produced by the generator.

## How the MCP Server Works

1. **Triage** – `assess_delegation_need` judges if a task deserves agentic decomposition, taking your available tool list into account.
2. **Planning** – `design_agentic_solution` calls a planner model that emits a dependency DAG, agent manifests, structured input/output schemas, and environment requirements.
3. **Implementation** – The same call dispatches a coding agent that emits runnable Agents SDK Python code aligned with the plan.
4. **Execution Simulation** – `execute_agentic_workflow` persists the generated file under `agentic_workflows/` and simulates a run, producing per-agent traces and shared artifacts.
5. **Evaluation & Feedback** – `evaluate_agentic_outputs` grades the simulation, while `summarize_agent_feedback` distills the findings so you can `revise_agentic_solution`.
6. **Closed-Loop Automation** – `run_agentic_cycle` chains the above steps until the workflow hits a target score or max iterations.

Whenever you pass an `available_tools` list, the server merges it with Codex core plus these MCP endpoints, ensuring downstream agents know they can invoke Codex again and keep breaking tasks down.

## Installation

```bash
cd agentic_flow_designer
pip install -r <(python3 - <<'PY'
import json, pathlib
manifest = json.loads(pathlib.Path("manifest.json").read_text())
print(" ".join(manifest["servers"][0]["requirements"]))
PY
)
```

Export the OpenAI credentials (and optionally a custom base URL) that the underlying planner/coder/evaluator models need:

```bash
export OPENAI_API_KEY=sk-...
# export OPENAI_BASE_URL=https://api.openai.com/v1
```

## Registering With Codex CLI

1. From this repository, ensure the launcher is executable:
   ```bash
   chmod +x agentic_flow_designer/run_server.sh
   ```
2. Remove any prior registration (optional):
   ```bash
   codex mcp remove agentic-flow-designer
   ```
3. Add the updated tool, pointing Codex at the helper script so it can manage the working directory and logging:
   ```bash
   codex mcp add agentic-flow-designer \
     /mnt/c/Users/jyoth/Desktop/om_Lakshmeya_namaha/ditra/codex_tools/agentic_flow_designer/run_server.sh
   ```

After registration, the Codex CLI can invoke these tools on demand. Include a default instruction in `~/.codex/config.toml` if you want Codex to reach for them automatically when tasks look multi-step:

```toml
[profiles.default]
instructions = [
  "When tasks look multi-step or quality-critical, call the agentic-flow-designer MCP tools (triage → plan → execute → evaluate) before replying."
]
```

## Usage From Codex CLI

With the MCP server running, Codex can call the tools organically during a chat. You can also trigger them manually using MCP tool commands, e.g.:

```bash
codex mcp call agentic-flow-designer design_agentic_solution \
  --task "Ship a Slack bot that posts daily sales metrics" \
  --available_tools '["internal-metrics-api", "slack_webhook"]'
```

The tool returns both the structured plan and the generated Agents SDK code path. Follow up with `execute_agentic_workflow` or `run_agentic_cycle` to simulate execution, gather feedback, and iterate until the plan meets your target quality.

Logs stream to `agentic_flow_designer/server.log`, making it easy to tail the live activity while Codex interacts with the tool.
