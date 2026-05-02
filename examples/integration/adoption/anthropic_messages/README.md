# Anthropic Messages → FlightDeck

```bash
uv sync --frozen --extra dev --extra anthropic
uv run python examples/integration/adoption/anthropic_messages/emit_run.py \
  --release-id rel_yourregisteredid --agent-id agent_support
```

Add **`--ingest`** to POST. Add **`--live`** for a real **`messages.create`** call (**`ANTHROPIC_API_KEY`**).
