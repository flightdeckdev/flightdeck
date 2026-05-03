# FlightDeck HTTP API

`flightdeck serve` exposes a local JSON API used by the web UI (`/`), the Python SDK
(`flightdeck.sdk`), and direct CLI automation. The server binds to `127.0.0.1:8765` by
default and is intended for **local development and CI**, not public exposure.

## Starting the server

```bash
flightdeck serve                         # default: 127.0.0.1:8765
flightdeck serve --port 9000            # custom port
flightdeck serve --host 0.0.0.0         # non-loopback (prints warning; see Security)
flightdeck serve --sqlite-lock-timeout 45 --retry-sqlite-lock  # SQLite busy/locked retries (default 30s on)
```

The server requires a `flightdeck.yaml` in the working directory. Run `flightdeck init`
first if it does not exist.

## Authentication and access control

Two access tiers:

| Route | No token configured | `FLIGHTDECK_LOCAL_API_TOKEN` set |
|-------|--------------------|---------------------------------|
| `GET /health` | open | open |
| `GET /v1/*` (reads: workspace, metrics, releases, promoted, actions, promotion-requests, runs, runs/export) | open | `Authorization: Bearer <token>` required |
| `POST /v1/events` | loopback only | `Authorization: Bearer <token>` required |
| `POST /v1/diff` | open | open |
| `POST /v1/promote` | loopback only | `Authorization: Bearer <token>` required |
| `POST /v1/promote/request`, `POST /v1/promote/confirm` | loopback only | `Authorization: Bearer <token>` required |
| `POST /v1/rollback` | loopback only | `Authorization: Bearer <token>` required |

`POST /v1/events` uses the **same** loopback / Bearer gate as promote and rollback
(`require_ledger_write_access` in `server/mutation_access.py`). **`GET /v1/*`** uses
`require_protected_read_access`: with a token set, send the same **`Authorization: Bearer`**
header (Python SDK **`api_token=`**). Remote agents must set `FLIGHTDECK_LOCAL_API_TOKEN` on
the server and send matching Bearer headers when using non-loopback hosts. When no token is
configured, only loopback callers (`127.0.0.1`, `::1`, `localhost`) may append run events, so
binding `--host 0.0.0.0` does not leave ingest open to arbitrary clients on the network.

```bash
export FLIGHTDECK_LOCAL_API_TOKEN="$(openssl rand -hex 32)"
flightdeck serve
```

See [SECURITY.md](../SECURITY.md) for the full trust model.

## Base URL

All paths below are relative to the server base URL, e.g. `http://127.0.0.1:8765`.

---

## `GET /health`

Health probe. Always returns HTTP 200 while the server is up.

**Response**

```json
{"status": "ok", "mutation_auth": "loopback", "read_auth": "open"}
```

`mutation_auth` and `read_auth` are always present on current servers:

- **`mutation_auth`:** `"loopback"` — no API token; ledger writes (including **`POST /v1/events`**) are allowed only from loopback clients. `"bearer"` — token set; writes require `Authorization: Bearer <that value>` from any host.
- **`read_auth`:** `"open"` — no API token; **`GET /v1/*`** need no Bearer. `"bearer"` — token set; read APIs require the same Bearer header as writes.

Neither field includes secret material.

**SQLite contention:** parallel writers against the **same** workspace SQLite file can see `database is locked`. The server retries locked/busy statements for a bounded time (CLI **`--sqlite-lock-timeout`** / **`--no-retry-sqlite-lock`**, env **`FLIGHTDECK_SQLITE_LOCK_TIMEOUT_S`**, **`FLIGHTDECK_SQLITE_RETRY_ON_LOCK`**, **`FLIGHTDECK_SQLITE_BUSY_TIMEOUT_MS`** for `PRAGMA busy_timeout`). CI and multi-process setups should still use **one workspace path per concurrent server** or switch to **`database_url`** (PostgreSQL) for multi-writer throughput — see **[operations-and-policy.md](operations-and-policy.md#sqlite-concurrency-and-postgresql)**.

---

## `GET /v1/metrics`

Read-only JSON snapshot of aggregate counts in the local SQLite ledger (releases, pricing tables, run events, promotion pointers, audit actions). Intended for simple operators or scrapers; this is **not** Prometheus exposition format.

**Response**

```json
{
  "counters": {
    "releases_total": 3,
    "pricing_tables_total": 1,
    "run_events_total": 120,
    "promoted_pointers_total": 1,
    "actions_total": 5,
    "actions_by_action": { "promote": 4, "rollback": 1 }
  },
  "schema_version": 4,
  "generated_at": "2026-05-03T12:00:00+00:00"
}
```

`schema_version` matches the highest applied SQLite migration (`LATEST_SCHEMA_MIGRATION_VERSION` in `flightdeck.storage`).

---

## `GET /v1/workspace`

Read-only flags derived from `flightdeck.yaml` plus the running package version. Used by the web UI and automation to choose **direct promote** vs **request/confirm** without embedding workspace YAML in the client. No secrets and no catalog file contents — only whether a **non-empty** `pricing_catalog_path` is set (`pricing_catalog_configured`).

**Response** (`WorkspacePublic` — see `schemas/v1/workspace_public.schema.json`)

```json
{
  "api_version": "v1",
  "kind": "WorkspacePublic",
  "promotion_requires_approval": false,
  "pricing_catalog_configured": false,
  "server_version": "1.1.2"
}
```

---

## `GET /v1/releases`

List all registered releases.

**Response**
```json
{
  "releases": [
    {
      "release_id": "rel_abc123",
      "agent_id": "agent_support",
      "version": "1.2.0",
      "environment": "production",
      "checksum": "a3f1c2e4b5d6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
      "created_at": "2026-05-01T12:00:00+00:00"
    }
  ]
}
```

`checksum` is a **64-character lowercase hex string** (raw SHA-256; no `sha256:` prefix). The
same value is printed with a `sha256=` label by `flightdeck release show` and
`flightdeck release verify` for human readability, but the stored and returned value is the
bare hex.

---

## `GET /v1/promoted`

List the currently promoted release for each `agent_id` / `environment` pair.

**Response**
```json
{
  "promoted": [
    {
      "agent_id": "agent_support",
      "environment": "production",
      "release_id": "rel_abc123"
    }
  ]
}
```

---

## `GET /v1/actions`

List promotion and rollback actions from the audit ledger.

Results are returned **newest first** (`ORDER BY created_at DESC`), so the most recent action
is always the first element in the array.

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent` | string | — | Filter by `agent_id` |
| `env` | string | — | Filter by environment |
| `limit` | integer | 50 | Max records returned (1–500); server enforces a minimum of 1 and a maximum of 500 |

**Response**
```json
{
  "actions": [
    {
      "action_id": "act_def456",
      "action": "promote",
      "release_id": "rel_abc123",
      "agent_id": "agent_support",
      "environment": "production",
      "baseline_release_id": "rel_prev789",
      "reason": "passed all staging checks",
      "policy_passed": true,
      "policy_reasons": ["first promotion: no promoted baseline for agent/environment"],
      "created_at": "2026-05-01T13:00:00+00:00",
      "audit_seq": 1
    }
  ]
}
```

`audit_seq` is a monotonically increasing integer assigned at insert time; `flightdeck
doctor` checks that the sequence has no gaps.

---

## `GET /v1/promotion-requests`

List promotion approval requests. Newest first.

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | — | Filter by status (`pending`, `completed`, `cancelled`) |
| `limit` | integer | 50 | Max rows (1–500) |

**Response**

```json
{
  "requests": [
    {
      "request_id": "prq_abc123",
      "status": "pending",
      "release_id": "rel_xyz",
      "agent_id": "agent_support",
      "environment": "production",
      "window": "7d",
      "reason": "rollout candidate",
      "actor": "ci",
      "baseline_release_id": "rel_prev",
      "policy": { "passed": true, "reasons": [], "evaluated_at": "2026-05-02T12:00:00+00:00" },
      "created_at": "2026-05-02T12:00:00+00:00",
      "resolved_at": null,
      "completed_action_id": null
    }
  ]
}
```

---

## `GET /v1/runs`

Read-only forensics: return a slice of ingested run events for one release (newest first).

**Query parameters (required in bold)**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **`release_id`** | string | — | Registered release |
| **`window`** | string | — | Same format as diff (`7d`, `24h`, `30m`) |
| `environment` | string | — | Defaults to workspace `default_environment` |
| `tenant_id` | string | — | Optional filter |
| `task_id` | string | — | Optional filter |
| `trace_id` | string | — | Optional filter: exact match on `RunEvent.request.trace_id` (ingested JSON path `request.trace_id`) |
| `session_id` | string | — | Optional filter: exact match on `request.session_id` |
| `span_id` | string | — | Optional filter: exact match on `request.span_id` |
| `offset` | integer | 0 | Skip this many newest-matching events before returning the page (0–500000) |
| `limit` | integer | 100 | Max events returned (1–500) |

**Response**

```json
{
  "release_id": "rel_abc",
  "since": "2026-04-25T12:00:00+00:00",
  "until": "2026-05-02T12:00:00+00:00",
  "filters": { "environment": "local", "tenant_id": null, "task_id": null, "trace_id": null, "session_id": null, "span_id": null },
  "offset": 0,
  "limit": 10,
  "matched_total": 42,
  "returned": 10,
  "truncated": true,
  "events": []
}
```

Each element of `events` is a `RunEvent` object (`schemas/v1/run_event.schema.json`).

---

## `GET /v1/runs/export`

Same **query parameters** and filter semantics as **`GET /v1/runs`** (defaults: **`offset`** `0`, **`limit`** `500`). Response body is **NDJSON**: one JSON object per line, each a `RunEvent` (`schemas/v1/run_event.schema.json`). **`Content-Type`:** `application/x-ndjson`.

Response headers (non-secret hints for clients):

| Header | Meaning |
|--------|---------|
| `X-Flightdeck-Matched-Total` | Count of events matching filters in the window |
| `X-Flightdeck-Returned` | Lines in this response body |
| `X-Flightdeck-Offset` | `offset` query value used |
| `X-Flightdeck-Truncated` | `true` if more matching events exist after this page |

---

## `POST /v1/events`

Ingest `RunEvent` records (runtime evidence for diff and policy evaluation).

**Auth:** Same as promote/rollback — loopback-only when `FLIGHTDECK_LOCAL_API_TOKEN` is unset;
otherwise `Authorization: Bearer <token>` required (see [Authentication and access control](#authentication-and-access-control)).

**Request body**
```json
{
  "events": [
    {
      "api_version": "v1",
      "type": "run_end",
      "timestamp": "2026-05-01T12:34:56Z",
      "agent_id": "agent_support",
      "release_id": "rel_abc123",
      "run_id": "run_unique_001",
      "tenant_id": "tenant_a",
      "task_id": "resolve_ticket",
      "environment": "production",
      "metrics": {
        "success": true,
        "latency_ms": 820,
        "error_type": null
      },
      "usage": {
        "model": {
          "provider": "openai",
          "model": "gpt-4o",
          "input_tokens": 1200,
          "output_tokens": 400,
          "cached_input_tokens": 0
        },
        "tools": []
      }
    }
  ]
}
```

`api_version` may be omitted (defaults to `"v1"`). Any other value — including `""`,
`null`, wrong case like `"V1"`, or unknown strings — returns HTTP 400 with a message of
the form `"Unsupported api_version for POST /v1/events: <value> (only 'v1' is accepted)."`.

`run_id` must be unique per workspace; duplicates are silently ignored by storage.

The `events` array must contain **at least one event**. An empty array (`"events": []`)
is rejected by Pydantic validation with HTTP **422** before any event processing occurs.

**Response**
```json
{"inserted": 1}
```

`inserted` is the count of **newly written** rows. Events with a `run_id` that already
exists in storage are silently skipped; they do not increment `inserted` and do not
produce an error.

**Errors**
- HTTP 400 — unsupported `api_version` value, or a field in a `RunEvent` fails type/range
  validation after the per-event `api_version` check. Field validation errors include
  the prefix `"Invalid RunEvent: "` in the `detail` string, e.g.
  `"Invalid RunEvent: 1 validation error for RunEvent …"`. Client code that parses
  error messages can key off this prefix to distinguish per-event validation failures
  from `api_version` rejections.
- HTTP 422 — `events` array is empty or the request body does not match the expected shape
  (Pydantic validation error; returned as an array under `detail`).

Full field reference: [`schemas/v1/run_event.schema.json`](../schemas/v1/run_event.schema.json).

### `RunEvent` field reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_version` | `"v1"` | no (defaults to `"v1"`) | Must be `"v1"` or omitted. Any other value returns HTTP 400. |
| `type` | `"run_start"` \| `"run_end"` | no (defaults to `"run_end"`) | Event type. Only `"run_end"` events carry cost/latency data; `"run_start"` is accepted but contributes no usage. |
| `timestamp` | ISO-8601 string | **yes** | Event timestamp. Used for time-window filtering in diff queries. |
| `workspace_id` | string | no (defaults to `"ws_local"`) | Workspace identifier. Stored with the event but **not used as a query filter** — diff queries filter on `release_id`, `tenant_id`, `task_id`, and `environment` only. |
| `agent_id` | string | **yes** | Stable agent identifier (must match the `spec.agent.agent_id` in the registered release). |
| `release_id` | string | **yes** | The `release_id` returned by `flightdeck release register`. Links the event to a release record. |
| `run_id` | string | **yes** | Unique run identifier per workspace. Duplicate `run_id` values are silently skipped. |
| `tenant_id` | string | **yes** | Tenant identifier. Used as a filter dimension in diff queries (`--tenant`). |
| `task_id` | string | **yes** | Task type identifier. Used as a filter dimension in diff queries (`--task`). |
| `environment` | string | **yes** | Deployment environment (e.g. `"production"`, `"staging"`). Must match the environment used in promote/rollback. |
| `metrics` | object | no | Run-level performance metrics (see below). |
| `usage` | object | **yes** | Model token usage (see below). |
| `labels` | object | no | Arbitrary string key-value pairs for tagging. Not used in diff/policy computations. |
| `request` | object | no | Tracing identifiers (`session_id`, `trace_id`, `span_id`). Not used in diff/policy computations. |

**`metrics` fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | boolean | `true` | Whether the run succeeded. `false` events contribute to the error rate in diff computations. |
| `latency_ms` | integer ≥ 0 | `null` | End-to-end run latency in milliseconds. Omit if not measured; `null` events are excluded from latency averages. |
| `error_type` | string | `null` | Optional error class (e.g. `"timeout"`, `"rate_limit"`). Informational only. |

**`usage` fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `usage.model.provider` | string | **yes** | LLM provider (e.g. `"openai"`). Must match the model's pricing table provider. |
| `usage.model.model` | string | **yes** | Model name (e.g. `"gpt-4o"`). Must have an entry in the release's pricing table. |
| `usage.model.input_tokens` | integer ≥ 0 | **yes** | Prompt tokens consumed. |
| `usage.model.output_tokens` | integer ≥ 0 | **yes** | Completion tokens generated. |
| `usage.model.cached_input_tokens` | integer ≥ 0 | no (default `0`) | Cached prompt tokens (used for cached rate pricing when a `cached_input_usd_per_1k_tokens` rate is set). |
| `usage.tools` | array | no | Per-tool usage entries (see below). Currently recorded but not factored into cost computations. |

**`usage.tools[]` entry fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tool_name` | string | **yes** | Tool identifier. |
| `invocations` | integer ≥ 0 | `0` | Number of times the tool was called. |
| `cost_units` | float ≥ 0 | `0.0` | Tool-specific cost units (vendor-defined; not yet used in cost computations). |

---

## `POST /v1/diff`

Compute a confidence-labeled diff between two registered releases over a time window.
This is a **read-only computation** — it does not change promoted pointers or write to
the audit ledger.

**Request body**
```json
{
  "baseline_release_id": "rel_prev789",
  "candidate_release_id": "rel_abc123",
  "window": "7d",
  "environment": null,
  "tenant_id": null,
  "task_id": null
}
```

`window` format: `{N}d` (days), `{N}h` (hours), `{N}m` (minutes). Required. `N` must be
a positive integer. Seconds and weeks are not supported. Examples: `"7d"`, `"24h"`,
`"30m"`. Invalid formats return HTTP 400.

`environment` defaults to `WorkspaceConfig.default_environment` when `null`.

**Time-window semantics:** run events are queried with `timestamp >= since AND timestamp <
until`. The interval is **half-open**: `since` is inclusive, `until` is exclusive. Both
boundaries are in UTC. `until` is set to the server's clock at the moment the request is
processed; `since` is `until - window_delta`. An event exactly at `until` is **not**
included.

**Response**
```json
{
  "window": "7d",
  "since": "2026-04-24T12:00:00+00:00",
  "until": "2026-05-01T12:00:00+00:00",
  "filters": {
    "environment": "production",
    "tenant_id": null,
    "task_id": null
  },
  "pricing": {
    "baseline_provider": "openai",
    "baseline_version": "2024-02",
    "baseline_model": "gpt-4o",
    "candidate_provider": "openai",
    "candidate_version": "2024-05",
    "candidate_model": "gpt-4o",
    "pricing_or_model_changed": true,
    "prices": {
      "baseline_input_usd_per_1k_tokens": 0.005,
      "baseline_output_usd_per_1k_tokens": 0.015,
      "baseline_cached_input_usd_per_1k_tokens": null,
      "candidate_input_usd_per_1k_tokens": 0.0045,
      "candidate_output_usd_per_1k_tokens": 0.0135,
      "candidate_cached_input_usd_per_1k_tokens": null
    },
    "warnings": [],
    "hints": [],
    "catalog": {
      "enabled": false,
      "catalog_version": null,
      "baseline_slot_id": null,
      "candidate_slot_id": null,
      "baseline_cost_per_run_usd": null,
      "candidate_cost_per_run_usd": null,
      "delta_cost_per_run_usd": null,
      "warnings": []
    }
  },
  "samples": {
    "baseline_runs": 1200,
    "candidate_runs": 850,
    "confidence": "HIGH",
    "confidence_reason": null
  },
  "metrics": {
    "baseline_cost_per_run_usd": 0.002341,
    "candidate_cost_per_run_usd": 0.002189,
    "delta_cost_per_run_usd": -0.000152,
    "delta_cost_per_run_pct": -0.065,
    "baseline_latency_ms_avg": 910.5,
    "candidate_latency_ms_avg": 875.2,
    "delta_latency_ms_avg": -35.3,
    "baseline_error_rate": 0.0083,
    "candidate_error_rate": 0.0071,
    "delta_error_rate": -0.0012
  },
  "policy": {
    "passed": true,
    "reasons": [],
    "evaluated_at": "2026-05-01T12:00:00+00:00"
  }
}
```

**`pricing.warnings`** — array of human-readable strings when the baseline or candidate
release's **`spec.runtime.model`** has no matching entry in that side's imported pricing
table. Per-side **`prices.*`** fields are **`null`** in that case. Warnings are **informational
only** and do not change **`policy`**. If ingested run events reference a model that cannot
be priced, the diff request still fails with HTTP 400 as before.

**`pricing.hints`** — optional diagnostics (for example other imported `pricing_version`
values for the same provider, or substring model-name hints when the exact model is missing).

**`pricing.catalog`** — when `flightdeck.yaml` sets `pricing_catalog_path` to a valid
`PricingCatalog` YAML, `enabled` is true and comparable per-run costs may appear using
operator-defined slot tariffs (additive; existing `metrics.*` semantics unchanged). See
`schemas/v1/pricing_catalog.schema.json` and `examples/pricing/catalog.sample.yaml`.

**Confidence levels**

| Label | Meaning |
|-------|---------|
| `HIGH` | Both baseline and candidate meet `min_baseline_runs` / `min_candidate_runs` |
| `MEDIUM` | At least one side is below its target but neither is below the floor |
| `LOW` | Either side is below `min_low_runs` |

Default thresholds (from `WorkspaceConfig.diff`): `min_candidate_runs=500`,
`min_baseline_runs=500`, `min_low_runs=50`. Override per-workspace or via the active policy.

**Errors**
- HTTP 400 — unknown release ID, missing pricing table, cross-agent diff (releases have
  different `agent_id`), inconsistent `agent_id` within one side's run events, or invalid
  `window` format. The `detail` field describes the specific problem.

---

## `POST /v1/promote`

Evaluate active policy and promote the release to the specified environment. Writes an
audit record regardless of whether policy passes; updates the promoted pointer only when
policy passes.

When **`promotion_requires_approval: true`** in `flightdeck.yaml`, this route returns HTTP
**400**; use **`POST /v1/promote/request`** then **`POST /v1/promote/confirm`** instead.

**Requires mutation access** (loopback client or Bearer token).

**Request body**
```json
{
  "release_id": "rel_abc123",
  "environment": "production",
  "window": "7d",
  "reason": "passed all staging checks",
  "actor": "ci-bot"
}
```

`reason` must be non-empty. `actor` defaults to `"http"`.

**Response (policy passes)**
```json
{
  "action_id": "act_def456",
  "action": "promote",
  "release_id": "rel_abc123",
  "agent_id": "agent_support",
  "environment": "production",
  "baseline_release_id": "rel_prev789",
  "promoted_pointer_changed": true,
  "policy": {
    "passed": true,
    "reasons": [],
    "evaluated_at": "2026-05-01T13:00:00+00:00"
  }
}
```

**First promotion** (no prior baseline for this agent/environment): policy evaluation is
skipped and the release is promoted unconditionally with reason `"first promotion: no
promoted baseline for agent/environment"`.

**Policy-blocked response (HTTP 409)**

When the active policy blocks promotion, the server returns HTTP **409 Conflict**. The
action is still written to the audit ledger; only the promoted pointer is not updated.

```json
{
  "detail": {
    "message": "Promotion blocked by policy.",
    "outcome": {
      "action_id": "act_def456",
      "action": "promote",
      "release_id": "rel_abc123",
      "agent_id": "agent_support",
      "environment": "production",
      "baseline_release_id": "rel_prev789",
      "promoted_pointer_changed": false,
      "policy": {
        "passed": false,
        "reasons": ["candidate cost per run USD 0.006 exceeds max 0.005"],
        "evaluated_at": "2026-05-01T13:00:00+00:00"
      }
    }
  }
}
```

Check `detail.outcome.policy.reasons` for the specific constraints that failed.

**Errors**
- HTTP 400 — unknown release ID, missing pricing table, invalid window, or empty reason.
- HTTP 401 — Bearer token missing or invalid (when a token is configured).
- HTTP 403 — caller is not a loopback client and no token is configured.
- HTTP 409 — action recorded in the audit ledger but blocked by the active policy.

---

## `POST /v1/promote/request`

When **`promotion_requires_approval: true`** in `flightdeck.yaml`, create a **pending**
promotion after the same policy evaluation as `/v1/promote` would run. If policy fails,
returns HTTP **409** with a JSON `detail.message` (no `promotion_requests` row is written).
If policy passes, returns **`request_id`** for **`POST /v1/promote/confirm`**.

**Requires mutation access.** Request body matches `/v1/promote` (`release_id`, `environment`, `window`, `reason`, optional `actor`).

If `promotion_requires_approval` is **false**, returns HTTP **400**.

---

## `POST /v1/promote/confirm`

Complete a pending request from **`/v1/promote/request`**. Body: `request_id`,
`approval_reason` (non-empty), optional `actor`. Re-runs promotion evaluation; on success
marks the request **completed** and returns the same shape as **`POST /v1/promote`**.

**Requires mutation access.**

---

## `POST /v1/rollback`

Roll back to a prior release. Identical contract to `/v1/promote` but with `"action":
"rollback"` in the response and `"message": "Rollback blocked by policy."` in the 409
body. A promoted baseline must already exist; rolling back when nothing is promoted
returns HTTP 400.

**Requires mutation access** (loopback client or Bearer token).

**Request body** — same shape as `/v1/promote`.

**Response (policy passes)** — same shape as `/v1/promote` with `"action": "rollback"`.

**Policy-blocked response** — same 409 shape as `/v1/promote` with `"action": "rollback"`
and `"message": "Rollback blocked by policy."`.

---

## Error response format

FastAPI returns errors as:

```json
{"detail": "human-readable error message"}
```

Validation errors (Pydantic) return an array under `detail`:

```json
{
  "detail": [
    {
      "loc": ["body", "events", 0, "run_id"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

## Interactive docs (Swagger UI)

When the server is running, visit `http://127.0.0.1:8765/docs` for auto-generated
OpenAPI documentation, or `http://127.0.0.1:8765/openapi.json` for the raw schema.
