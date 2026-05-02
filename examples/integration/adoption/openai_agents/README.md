# OpenAI Agents SDK → FlightDeck

Install **`flightdeck-ai[integrations-openai-agents]`** (see root **`pyproject.toml`**). The
helper **duck-types** the run result object; verify fields against your installed SDK version.

```bash
uv sync --frozen --extra dev --extra integrations-openai-agents
uv run python examples/integration/adoption/openai_agents/emit_run.py \
  --release-id rel_yourregisteredid --agent-id agent_support
```
