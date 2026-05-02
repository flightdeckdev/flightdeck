# Temporal → FlightDeck labels

FlightDeck does not import **`temporalio`** in core. Use **`temporal_labels`** from
**`flightdeck.integrations.common`** (or copy the dict keys) so **`RunEvent.labels`** correlate
ledger rows with **`workflow_id`** / **`run_id`**.

```bash
uv sync --frozen --extra dev
uv run python examples/integration/adoption/temporal/emit_run.py \
  --release-id rel_yourregisteredid --agent-id agent_support
```

Optional: install **`flightdeck-ai[integrations-temporal]`** if your worker code shares that venv
for other reasons; this example only needs **`make_run_end_event`**.
