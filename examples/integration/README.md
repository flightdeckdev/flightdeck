# Runtime integration (event emitters)

These examples show how application or agent runtimes can **push evidence** into FlightDeck over **`POST /v1/events`** (same contract as **`flightdeck runs ingest`**).

**Framework adoption:** [adoption/](adoption/README.md) — optional **`flightdeck.integrations`** helpers and per-vendor scripts (see also **[docs/sdk-integrations.md](../../docs/sdk-integrations.md)**).

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

### After ingest

Use **`flightdeck release diff`**, **`POST /v1/diff`** (same JSON as **`release diff --output json`**), or the bundled UI at **`/#/diff`** to compare baseline vs candidate over a window once both releases are registered and run evidence exists. CI pattern: [examples/ci/README.md](../ci/README.md).

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
  ${FLIGHTDECK_LOCAL_API_TOKEN:+-H "Authorization: Bearer $FLIGHTDECK_LOCAL_API_TOKEN"} \
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

The **`Authorization`** line is omitted when **`FLIGHTDECK_LOCAL_API_TOKEN`** is unset (loopback-only ingest). When the server uses a token, export it (or pass an explicit **`-H 'Authorization: Bearer …'`**).

Without **`jq`**, paste a static JSON file or use the Node script below.

### Node (`emit_sample_events.node.mjs`)

Uses built-in **`fetch`** (Node **18+**). No npm dependencies:

```bash
node examples/integration/emit_sample_events.node.mjs \
  --base-url http://127.0.0.1:8765 \
  --release-id rel_yourregisteredid \
  --agent-id agent_support \
  ${FLIGHTDECK_LOCAL_API_TOKEN:+--api-token "$FLIGHTDECK_LOCAL_API_TOKEN"}
```

### Trust boundaries

**`POST /v1/events`** is a ledger write: without **`FLIGHTDECK_LOCAL_API_TOKEN`**, only **loopback**
callers may ingest; with a token set, callers must send **`Authorization: Bearer`** (the Python
SDK uses **`api_token=`**). Treat remote access like any other sensitive control plane. See
**[SECURITY.md](../../SECURITY.md)** and **[docs/http-api.md](../../docs/http-api.md)**.

When using **`curl`**, add **`-H "Authorization: Bearer $FLIGHTDECK_LOCAL_API_TOKEN"`** if the
server is configured with a local API token.
