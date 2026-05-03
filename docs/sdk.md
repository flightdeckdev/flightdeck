# FlightDeck Python SDK

`flightdeck.sdk` is a thin HTTP client for emitting runtime evidence and triggering release
actions against a running `flightdeck serve` instance. It ships with the same SemVer as the
CLI; see [RELEASE_NOTES.md](../RELEASE_NOTES.md) for stability expectations. Internally,
**`flightdeck.sdk.http_common`** holds shared URL/header helpers, JSON/query serializers, and
retry loops so **`FlightdeckClient`** (sync) and **`AsyncFlightdeckClient`** stay wire-identical.

For most workflows the CLI is sufficient. Use the SDK when you need to:

- emit `RunEvent` records from inside an agent process (no JSONL file needed)
- drive diff / promote / rollback from Python (CI automation, notebooks)
- integrate FlightDeck into an async service

## Installation

```bash
pip install 'flightdeck-ai'
# or
uv add flightdeck-ai
```

Optional **LangChain / Temporal / OpenAI Agents** mappers ship under **`flightdeck.integrations`**
(experimental; separate extras). See **[sdk-integrations.md](sdk-integrations.md)** and
**[examples/integration/adoption/](../examples/integration/adoption/README.md)**.

## Quick start

```python
from flightdeck.sdk import FlightdeckClient
from flightdeck.models import RunEvent
from datetime import datetime, timezone

client = FlightdeckClient("http://127.0.0.1:8765")

# Confirm the server is reachable
print(client.health())  # {"status": "ok"}

# Emit a single run event
event = RunEvent(
    timestamp=datetime.now(timezone.utc),
    agent_id="agent_support",
    release_id="rel_abc123",
    run_id="run_unique_001",
    tenant_id="tenant_a",
    task_id="resolve_ticket",
    environment="production",
    usage={
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "input_tokens": 1200,
            "output_tokens": 400,
        }
    },
    metrics={"success": True, "latency_ms": 820},
)
client.ingest_run_events([event])
client.close()
```

## Constructor parameters

```python
FlightdeckClient(
    base_url: str,
    *,
    timeout_s: float = 5.0,        # per-request timeout
    max_retries: int = 0,           # extra attempts on transient network errors
    retry_backoff_s: float = 0.1,  # base backoff; doubles on each retry
    api_token: str | None = None,  # Bearer token when FLIGHTDECK_LOCAL_API_TOKEN is set
    client: httpx.Client | None = None,  # inject a pre-configured client
)
```

`AsyncFlightdeckClient` has identical parameters but takes `httpx.AsyncClient` and every
method is a coroutine. Call `await client.aclose()` instead of `client.close()`.

## Authentication

When `flightdeck serve` is started with `FLIGHTDECK_LOCAL_API_TOKEN` set, every **ledger write**
— **`POST /v1/promote`**, **`POST /v1/promote/request`**, **`POST /v1/promote/confirm`**,
**`POST /v1/rollback`**, and **`POST /v1/events`** (`ingest_run_events`) — requires the
matching Bearer token on the `FlightdeckClient` (`api_token=…`). The same token is required
for **`GET /v1/*`** read APIs (`get_workspace`, `list_runs`, …). With no token configured on the
server, writes accept only **loopback** callers and reads are open; **`POST /v1/diff`** stays
unauthenticated regardless.

```python
client = FlightdeckClient(
    "http://127.0.0.1:8765",
    api_token="your-local-token",
)
```

See [SECURITY.md](../SECURITY.md) for the full access model.

## Methods

### `health() -> dict`

`GET /health` — returns `{"status": "ok", "mutation_auth": "…", "read_auth": "…"}` when the server is up (`mutation_auth` / `read_auth` describe write vs read Bearer policy; see **HTTP API**).

### `get_workspace() -> dict`

`GET /v1/workspace` — returns `WorkspacePublic` JSON: `promotion_requires_approval`, `pricing_catalog_configured` (whether `pricing_catalog_path` is set to a non-empty string), and `server_version` (installed `flightdeck-ai` SemVer). Same method exists on `AsyncFlightdeckClient`. See [http-api.md § GET /v1/workspace](http-api.md#get-v1workspace).

### `GET /v1/metrics` (no SDK wrapper)

The metrics endpoint has no dedicated SDK method. Call it directly via `httpx` or `requests`:

```python
import httpx

resp = httpx.get("http://127.0.0.1:8765/v1/metrics")
resp.raise_for_status()
counters = resp.json()
# {
#   "counters": {
#     "releases_total": 3,
#     "pricing_tables_total": 1,
#     "run_events_total": 120,
#     "promoted_pointers_total": 1,
#     "actions_total": 5,
#     "actions_by_action": {"promote": 4, "rollback": 1}
#   },
#   "schema_version": 3,
#   "generated_at": "2026-05-03T12:00:00+00:00"
# }
```

`GET /v1/metrics` is read-only and requires no token. See [http-api.md § GET /v1/metrics](http-api.md#get-v1metrics) for the full response shape.

### `list_releases() -> dict`

`GET /v1/releases` — returns `{"releases": [...]}`. Each entry includes `release_id`,
`agent_id`, `version`, `environment`, `checksum`, and `created_at`.

### `list_promoted() -> dict`

`GET /v1/promoted` — returns `{"promoted": [...]}`. Each entry maps an `agent_id` +
`environment` pair to the currently promoted `release_id`.

### `list_actions(*, agent_id=None, environment=None, limit=50) -> dict`

`GET /v1/actions` — returns `{"actions": [...]}` filtered by the optional `agent_id`
and `environment` parameters. Each entry includes the action, policy result, reason, and
`audit_seq`.

### `ingest_run_events(events: Iterable[RunEvent]) -> int`

`POST /v1/events` — posts events in a single request. Returns the number inserted.
Pass `RunEvent` model instances (from `flightdeck.models`). Events with a duplicate
`run_id` are silently skipped by storage.

### `ingest_run_events_batch(events: Iterable[RunEvent], *, chunk_size=500) -> int`

Splits a large iterable into chunks of `chunk_size` and calls `ingest_run_events` on each.
Returns total events inserted. Raises `ValueError` if `chunk_size <= 0`.

### `post_diff(*, baseline_release_id, candidate_release_id, window, environment=None, tenant_id=None, task_id=None) -> dict`

`POST /v1/diff` — computes a confidence-labeled cost/latency/error-rate diff between two
registered releases. `window` is a string like `"7d"`, `"24h"`, or `"30m"`. Returns the
full diff payload (see [HTTP API reference](http-api.md)).

**Note:** `POST /v1/diff` does **not** require the mutation token — it is a read-only
computation.

### `post_promote(*, release_id, environment, window, reason, actor="sdk") -> dict`

`POST /v1/promote` — evaluates active policy and, if it passes, updates the promoted
pointer for the agent/environment. `reason` must be a non-empty string (required for the
audit log). Requires the mutation token if one is configured.

### `post_rollback(*, release_id, environment, window, reason, actor="sdk") -> dict`

`POST /v1/rollback` — same contract as promote; rolls back to the specified release.

### `post_promote_request(…)` / `post_promote_confirm(…)`

`POST /v1/promote/request` and `POST /v1/promote/confirm` — two-step promotion when
`promotion_requires_approval` is enabled in `flightdeck.yaml`. Same mutation token rules
as `post_promote`.

### `list_promotion_requests(*, status=None, limit=50) -> dict`

`GET /v1/promotion-requests`.

### `list_runs(*, release_id, window, environment=None, tenant_id=None, task_id=None, trace_id=None, session_id=None, span_id=None, offset=0, limit=100) -> dict`

`GET /v1/runs` — read-only event slice for forensics. Optional `trace_id`, `session_id`, and `span_id` filter on `request.*` (exact match). `offset` skips the newest matching events before returning up to `limit` rows.

### `fetch_runs_export_ndjson(*, release_id, window, …) -> tuple[bytes, dict[str, str]]`

`GET /v1/runs/export` — same filters as `list_runs`; returns the raw **NDJSON** body and selected `X-Flightdeck-*` response headers.

## Async usage

```python
import asyncio
from flightdeck.sdk import AsyncFlightdeckClient

async def main():
    client = AsyncFlightdeckClient("http://127.0.0.1:8765")
    try:
        releases = await client.list_releases()
        print(releases)
    finally:
        await client.aclose()

asyncio.run(main())
```

## Context manager pattern

The clients do not implement `__enter__`/`__exit__` directly, but you can wrap them:

```python
client = FlightdeckClient("http://127.0.0.1:8765")
try:
    count = client.ingest_run_events_batch(all_events)
finally:
    client.close()
```

## Error handling

All methods call `response.raise_for_status()` before returning, so HTTP 4xx/5xx
responses raise `httpx.HTTPStatusError`. Transient network failures raise
`httpx.RequestError` and are retried up to `max_retries` times with exponential backoff.

**Policy-blocked promote/rollback (HTTP 409)**

When the active policy blocks a `post_promote` or `post_rollback` call, the server returns
HTTP 409. The SDK raises `httpx.HTTPStatusError`; the full outcome — including which
policy constraints failed — is in `e.response.json()["detail"]`.

```python
import httpx

try:
    result = client.post_promote(
        release_id="rel_abc123",
        environment="production",
        window="7d",
        reason="tested in staging",
    )
except httpx.HTTPStatusError as e:
    if e.response.status_code == 409:
        detail = e.response.json()["detail"]
        # detail["message"]  -> "Promotion blocked by policy."
        # detail["outcome"]["policy"]["reasons"] -> list of failed constraints
        print("Blocked:", detail["outcome"]["policy"]["reasons"])
    else:
        raise
```

The action is still recorded in the audit ledger even when blocked; `GET /v1/actions`
will show it with `policy_passed: false`.

## Custom `httpx.Client`

Inject a pre-configured client to set custom SSL certificates, proxies, or connection
limits:

```python
import httpx
from flightdeck.sdk import FlightdeckClient

http = httpx.Client(verify="/path/to/ca.pem", timeout=30.0)
client = FlightdeckClient("http://127.0.0.1:8765", client=http)
# client does not own `http`; caller is responsible for closing it.
```

When `client` is passed, `FlightdeckClient` sets `_owns_client = False` and `close()` is
a no-op for the injected client.

## Constraints

- The SDK targets the same CPython version range as the CLI (`>=3.11,<4` from **v1.2**).
- `httpx` is a required dependency of `flightdeck-ai`; it is not optional.
- `RunEvent` instances must have `api_version = "v1"` (the default). The server rejects
  other values with HTTP 400.
- `ingest_run_events` returns `0` immediately if the event list is empty without making a
  network request.
