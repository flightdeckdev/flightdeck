# FlightDeck HTTP API

`flightdeck serve` exposes a local JSON API used by the web UI (`/`), the Python SDK
(`flightdeck.sdk`), and direct CLI automation. The server binds to `127.0.0.1:8765` by
default and is intended for **local development and CI**, not public exposure.

## Starting the server

```bash
flightdeck serve                         # default: 127.0.0.1:8765
flightdeck serve --port 9000            # custom port
flightdeck serve --host 0.0.0.0         # non-loopback (prints warning; see Security)
```

The server requires a `flightdeck.yaml` in the working directory. Run `flightdeck init`
first if it does not exist.

## Authentication and access control

Two access tiers:

| Route | No token configured | `FLIGHTDECK_LOCAL_API_TOKEN` set |
|-------|--------------------|---------------------------------|
| `GET /health` | open | open |
| `GET /v1/*` (reads) | open | open |
| `POST /v1/events` | loopback only† | open (no Bearer required) |
| `POST /v1/diff` | open | open |
| `POST /v1/promote` | loopback only | `Authorization: Bearer <token>` required |
| `POST /v1/rollback` | loopback only | `Authorization: Bearer <token>` required |

†`POST /v1/events` is not behind the Bearer gate but the server only listens on loopback
 by default, so it remains local-only unless `--host` is overridden.

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
{"status": "ok"}
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
      "checksum": "sha256:...",
      "created_at": "2026-05-01T12:00:00+00:00"
    }
  ]
}
```

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

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent` | string | — | Filter by `agent_id` |
| `env` | string | — | Filter by environment |
| `limit` | integer | 50 | Max records returned (1–500) |

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

## `POST /v1/events`

Ingest `RunEvent` records (runtime evidence for diff and policy evaluation).

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

`api_version` may be omitted (defaults to `"v1"`). Any other value returns HTTP 400.
`run_id` must be unique per workspace; duplicates are silently ignored by storage.

**Response**
```json
{"inserted": 1}
```

**Errors**
- HTTP 400 — unsupported `api_version` or malformed `RunEvent` field.

Full field reference: [`schemas/v1/run_event.schema.json`](../schemas/v1/run_event.schema.json).

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

`window` format: `{N}d` (days), `{N}h` (hours), `{N}m` (minutes). Required.
`environment` defaults to `WorkspaceConfig.default_environment` when `null`.

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
    "pricing_or_model_changed": true
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

**Confidence levels**

| Label | Meaning |
|-------|---------|
| `HIGH` | Both baseline and candidate meet `min_baseline_runs` / `min_candidate_runs` |
| `MEDIUM` | At least one side is below its target but neither is below the floor |
| `LOW` | Either side is below `min_low_runs` |

Default thresholds (from `WorkspaceConfig.diff`): `min_candidate_runs=500`,
`min_baseline_runs=500`, `min_low_runs=50`. Override per-workspace or via the active policy.

**Errors**
- HTTP 400 — unknown release ID, missing pricing table, cross-agent diff, or invalid
  `window` format. The `detail` field describes the specific problem.

---

## `POST /v1/promote`

Evaluate active policy and promote the release to the specified environment. Writes an
audit record regardless of whether policy passes; updates the promoted pointer only when
policy passes.

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

**Response**
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

When `promoted_pointer_changed` is `false`, policy did not pass — the release was **not**
promoted. Check `policy.reasons` for the failure details.

**First promotion** (no prior baseline for this agent/environment): policy evaluation is
skipped and the release is promoted unconditionally with reason `"first promotion: no
promoted baseline for agent/environment"`.

**Errors**
- HTTP 400 — unknown release ID, missing pricing table, invalid window, or empty reason.
- HTTP 401 — Bearer token missing or invalid (when a token is configured).
- HTTP 403 — caller is not a loopback client and no token is configured.

---

## `POST /v1/rollback`

Roll back to a prior release. Identical contract to `/v1/promote` but with `"action":
"rollback"` in the response. A promoted baseline must already exist; rolling back when
nothing is promoted returns HTTP 400.

**Requires mutation access** (loopback client or Bearer token).

**Request body** — same shape as `/v1/promote`.

**Response** — same shape as `/v1/promote` with `"action": "rollback"`.

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
