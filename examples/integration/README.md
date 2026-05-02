# Runtime integration (event emitters)

These examples show how application or agent runtimes can **push evidence** into FlightDeck over **`POST /v1/events`** (same contract as **`flightdeck runs ingest`**).

## Prerequisites

- A running **`flightdeck serve`** (local CLI or **[examples/deploy](../deploy/README.md)**).
- A **registered** `release_id` (from **`flightdeck release register …`**) whose `agent_id` and model match the events you emit.

## Python (`emit_sample_events.py`)

Uses the shipped SDK (**`FlightdeckClient.ingest_run_events`**) and Pydantic **`RunEvent`** models.

From a clone with **uv**:

```bash
uv sync --frozen --extra dev
uv run python examples/integration/emit_sample_events.py \
  --base-url http://127.0.0.1:8765 \
  --release-id rel_yourregisteredid \
  --agent-id agent_support
```

With an activated venv where **`flightdeck-ai`** is installed:

```bash
python examples/integration/emit_sample_events.py --release-id rel_abc123 --agent-id agent_support
```

### Wire format

The HTTP body is `{"events": [<RunEvent>, ...]}` with **`api_version`: `"v1"`**. Field reference: **[docs/http-api.md](../../docs/http-api.md)** and **`schemas/v1/run_event.schema.json`**.

### Trust boundaries

Anyone who can reach **`POST /v1/events`** can append ledger rows for a `release_id` they guess. Keep **`serve`** on loopback or a private network, or front it with your own controls. See **[SECURITY.md](../../SECURITY.md)**.
