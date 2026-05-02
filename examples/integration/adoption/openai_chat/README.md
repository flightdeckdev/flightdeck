# OpenAI Chat Completions → FlightDeck

```bash
uv sync --frozen --extra dev --extra openai
uv run python examples/integration/adoption/openai_chat/emit_run.py \
  --release-id rel_yourregisteredid --agent-id agent_support
```

Prints a synthetic completion payload as JSON. Add **`--ingest`** to **`POST /v1/events`** while
**`flightdeck serve`** is running. Add **`--live`** for a real completion (requires
**`OPENAI_API_KEY`**).
