# Agentic Flow Designer MCP Tool

This tool lets Codex spin up an optimal set of agents for a task. It first asks a planning agent to design the workflow, then dispatches a coding agent to emit production-ready OpenAI Agents SDK code for the planned flow.

## Installation

```bash
cd agentic_flow_designer
pip install -r <(python - <<'PY'
import json, pathlib
manifest = json.loads(pathlib.Path("manifest.json").read_text())
requirements = manifest["servers"][0]["requirements"]
print(" ".join(requirements))
PY
)
```

Set your API key (and optionally a custom base URL).

```bash
export OPENAI_API_KEY=sk-...
# export OPENAI_BASE_URL=https://api.openai.com/v1
```

## Running

Start the MCP server manually (optional):

```bash
python server.py
```

Register `agentic-flow-designer` with Codex, then let the agent decide which tool to call. When Codex determines agentic delegation will help, the new tools guide it through triage → planning → execution simulation → evaluation → revision automatically.

## Registering with Codex

The Codex CLI expects an absolute command for MCP servers. A helper script is provided so the CLI can launch the server with the right working directory and environment:

```bash
codex mcp remove agentic-flow-designer  # only if you registered an earlier version
codex mcp add agentic-flow-designer \
  "$(pwd)/agentic_flow_designer/run_server.sh"
```

After registration simply chat with Codex; when the assistant sees a complex task it can:

1. Call `assess_delegation_need` to decide whether agentic delegation will help.
2. Use `design_agentic_solution` (and `revise_agentic_solution` when needed) to build/iterate on agent code.
3. Simulate runs via `execute_agentic_workflow`, grade them with `evaluate_agentic_outputs`, summarise feedback, and loop through `run_agentic_cycle` for fully automated refinement.

Tip: Add a default instruction so Codex reaches for these tools automatically. In `~/.codex/config.toml` add something like:

```
[profiles.default]
instructions = [
  "When tasks look multi-step or quality-critical, call the agentic-flow-designer MCP tools (triage → plan → execute → evaluate) before replying."
]
```

Server logs (including Codex-triggered runs) are stored in `agentic_flow_designer/server.log`. Tail the file for real-time activity:

```bash
tail -f agentic_flow_designer/server.log
```

## Tool Suite

By default every planner/coder/evaluator call is told that Codex's core assistant and this MCP's full tool surface are available. Supplying `available_tools` simply augments that list with your domain-specific integrations so generated agents can keep delegating recursively while still respecting your environment.

### `assess_delegation_need`

Quick triage that returns `should_delegate`, `confidence`, and focus areas so Codex knows when to branch into agentic mode. Pass `available_tools` to ground the decision in reality.

### `design_agentic_solution`

Input:

- `task` *(required)*
- `available_tools` *(optional)* – enumerate concrete tools/APIs Codex can tap
- Optional model/temperature overrides

Output bundle includes:

- Dependency DAG (`execution_graph`) so agents can run in parallel
- Action manifests per agent with concrete commands
- Structured input/output schemas for artifact routing
- Environment prerequisites (env vars, secrets, validation commands)
- Generated Agents SDK code that enforces the DAG, validates prerequisites, and plumbs structured data

### `execute_agentic_workflow`

Writes the generated code to `./agentic_workflows/` (or a provided `workspace_path`) and simulates the run, returning per-agent outputs, artifacts, and merged context. Real execution can be added later; for now the simulator provides rich traces for evaluation.

### `evaluate_agentic_outputs`

Scores the execution report, flags blocking agents, and provides detailed improvement feedback. Supply an `evaluation_criteria` string to enforce quality bars or policy checks.

### `summarize_agent_feedback`

Turns the evaluation payload into a concise feedback summary (`summary`, `blocking_agents`) that feeds directly into `revise_agentic_solution` or the iterative cycle.

### `revise_agentic_solution`

Use when an earlier workflow needs adjustment. Provide the previous plan plus feedback (often from the evaluator/summary tools) and the planner regenerates the workflow, optionally reusing the previous implementation bundle.

### `run_agentic_cycle`

High-level orchestrator that chains planning, simulation, evaluation, and revision until the score crosses a `target_score` (default 0.85) or `max_iterations` is reached. Returns every iteration snapshot along with the final plan/code/evaluation so Codex can integrate the best result into its answer.
