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

### `curl` (no SDK)

Replace **`REL_ID`**, **`AGENT`**, and optionally **`BASE`** (default `http://127.0.0.1:8765`):

```bash
BASE=http://127.0.0.1:8765
REL_ID=rel_yourregisteredid
AGENT=agent_support
RUN_ID=emit-curl-$(date +%s)
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

curl -sS -X POST "$BASE/v1/events" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n \
    --arg rid "$REL_ID" \
    --arg aid "$AGENT" \
    --arg run "$RUN_ID" \
    --arg ts "$TS" \
    '{events:[{
      api_version:"v1", type:"run_end", timestamp:$ts,
      workspace_id:"ws_local", agent_id:$aid, release_id:$rid, run_id:$run,
      tenant_id:"tenant_example", task_id:"task_example", environment:"local",
      metrics:{latency_ms:250, success:true, error_type:null},
      usage:{model:{provider:"openai", model:"gpt-4.1-mini", input_tokens:400, output_tokens:120, cached_input_tokens:0}, tools:[]},
      labels:{source:"curl-example"}
    }]}')"
```

Without **`jq`**, paste a static JSON file or use the Node script below.

### Node (`emit_sample_events.node.mjs`)

Uses built-in **`fetch`** (Node **18+**). No npm dependencies:

```bash
node examples/integration/emit_sample_events.node.mjs \
  --base-url http://127.0.0.1:8765 \
  --release-id rel_yourregisteredid \
  --agent-id agent_support
```

### Trust boundaries

Anyone who can reach **`POST /v1/events`** can append ledger rows for a `release_id` they guess. Keep **`serve`** on loopback or a private network, or front it with your own controls. See **[SECURITY.md](../../SECURITY.md)**.
