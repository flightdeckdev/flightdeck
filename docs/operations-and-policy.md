# Operations and Policy

This document explains the core release governance logic: how `flightdeck release diff`,
`promote`, and `rollback` work under the hood, how CLI / HTTP / SDK all converge on the
same code, and how the policy system controls promotion gates.

For the on-disk formats these operations consume — `release.yaml`, bundle layout, checksum
algorithm, workspace config, and pricing table YAML — see
[release-artifact.md](release-artifact.md).

## Architecture: single operations layer

```
CLI (click)          HTTP routes (FastAPI)    Python SDK
      \                      |                   /
       \                     v                  /
        +------- flightdeck.operations --------+
                      |           |
              ledger.diff_releases  storage.*
```

`src/flightdeck/operations.py` is the single source of truth for all release actions.
The CLI (`cli/main.py`), the HTTP server (`server/routes/actions.py`), and the SDK
(`sdk/client.py`) all call it. There is no separate code path.

The three primary functions:

| Function | CLI command | HTTP route |
|----------|-------------|-----------|
| `compute_diff` | `flightdeck release diff` | `POST /v1/diff` |
| `promote_release` | `flightdeck release promote` | `POST /v1/promote` |
| `rollback_release` | `flightdeck release rollback` | `POST /v1/rollback` |

All raise `OperationError` (a `ValueError` subclass) for user-visible problems. The CLI
maps these to `click.ClickException`; the HTTP layer maps them to HTTP 400.

### Server initialization: lifespan vs. `ensure_app_state`

`server/app.py` registers a FastAPI **lifespan** handler that runs at startup:

```python
cfg = load_config()           # reads flightdeck.yaml from cwd
storage = Storage(cfg.db_path)
storage.migrate()
app.state.cfg = cfg
app.state.storage = storage
app.state.local_api_token = os.environ.get("FLIGHTDECK_LOCAL_API_TOKEN")
```

Every request handler then calls `ensure_app_state(request)` from
`server/routes/common.py`. That function returns `(cfg, storage)` immediately if
`app.state.cfg` and `app.state.storage` are already set. If they are **not** set (e.g. in
tests that construct the app without going through the full lifespan, or in unusual embedding
scenarios), it re-runs the same load-and-migrate sequence and stores the results on
`app.state`. This lazy fallback means tests can call routes without starting uvicorn, but
it also means the working directory at **first request time** determines which
`flightdeck.yaml` is loaded, not the directory at process start.

`_require_mutation_access` (called by `POST /v1/promote` and `POST /v1/rollback`) reads
`request.app.state.local_api_token` set during lifespan or lazy init. The test client host
`"testclient"` is included in `_LOCAL_CLIENT_HOSTS` alongside loopback addresses so that
integration tests can call mutation routes without a Bearer token.

---

## `compute_diff`

```python
compute_diff(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    baseline_release_id: str,
    candidate_release_id: str,
    window: str,          # e.g. "7d", "24h", "30m"
    environment: str | None,
    tenant_id: str | None,
    task_id: str | None,
) -> DiffOutcome
```

### Steps

1. Load both release records and validate their `ReleaseArtifact` shapes.
2. Reject cross-agent diffs (baseline and candidate must have the same `agent_id`).
3. Load the pricing table for each release (provider + pricing_version from
   `spec.pricing_reference`). Missing tables raise `OperationError` with a hint to run
   `flightdeck pricing import`.
4. Parse `window` into a `timedelta` via `ledger.parse_window`. Valid units are `d`
   (days), `h` (hours), and `m` (minutes) — seconds and weeks are not supported. The
   numeric part must be a positive integer; `"0h"`, `"-7d"`, and `"7w"` all raise
   `OperationError`. Compute `since = until - delta`, `until = now` (UTC at call time).
   Events are queried with `timestamp >= since AND timestamp < until` (half-open interval).
5. Query `run_events` for each release ID filtered by environment, tenant, task, and the
   time window.
6. Call `ledger.diff_releases` to compute per-side rollups (cost, latency, error rate),
   a confidence label, and a policy evaluation against the active policy.
7. Return a `DiffOutcome` dataclass with all computed values.

### Cost computation

Each `RunEvent` carries `usage.model.{input_tokens, output_tokens, cached_input_tokens}`.
The pricing table (loaded from `pricing_tables`) provides per-1k-token rates. Cost is:

```
cost = (input_tokens / 1000) * input_usd_per_1k
     + (output_tokens / 1000) * output_usd_per_1k
     + (cached_input_tokens / 1000) * cached_input_usd_per_1k  # only if rate is set
```

Runs are averaged across all events in the window to produce `cost_per_run_usd`.

### `compute_diff` vs. `promote_release` / `rollback_release`: filter scope

`compute_diff` supports optional `tenant_id` and `task_id` filters in addition to
`environment`. These allow you to narrow the evidence window to a specific tenant or task
type when comparing releases.

`_evaluate_promotion_or_rollback` (the shared path for `promote` and `rollback`) does
**not** accept tenant or task filters. It queries run events for the entire environment
over the window:

```python
# promote/rollback path — no tenant_id or task_id argument passed
storage.query_runs(release_id, since, until, environment=environment)
```

This means **policy evaluation for promote/rollback aggregates all runs in the
environment over the window**, regardless of tenant or task. The active policy applies to
the full population of events for that release, not a filtered slice. If you need
tenant-scoped evaluation, use `release diff` first to inspect the filtered evidence, then
decide whether to promote.

### Important constraint: cross-agent diffs

`compute_diff` checks that both releases have the same `agent_id` in their artifact
spec *before* querying events. This is checked again inside `diff_releases` if run events
from both sides are non-empty.

`diff_releases` also enforces that all events on a given side share a single `agent_id`.
If events for the baseline (or candidate) release span multiple agent IDs, the diff is
rejected with:

```
Each side of the diff must have a single consistent agent_id among run events.
```

This can happen if `run_id` values from different agents were ingested under the same
`release_id`. Ensure every `RunEvent` for a release carries the correct `agent_id`
matching `spec.agent.agent_id` in the release artifact.

### Diffs where one side has no run events

`diff_releases` only runs the cross-agent agent consistency check when **both** sides
have events. If one side (or both) has zero events in the window, the consistency check is
skipped. The rollup for the empty side evaluates to zero runs, zero cost, no latency data,
and zero error rate. Confidence is determined by the sample count thresholds as normal:

- With default thresholds (`min_candidate_runs=500`, `min_baseline_runs=500`,
  `min_low_runs=50`), a baseline with zero runs will produce `LOW` confidence.
- With all thresholds set to `0` (staging policy), zero events on either side can reach
  `HIGH` confidence.

**Practical implication:** if you register a new baseline with no run history and
immediately diff it against a candidate, the diff will complete without error, but
`baseline_runs` will be 0 and confidence will be `LOW` (or lower than `HIGH` with default
thresholds). This is a valid signal — it means the baseline has no observable data to
compare against.

### Pricing and model change detection

`DiffOutcome` includes a `pricing_or_model_changed` flag that is `True` when any of the
following differ between baseline and candidate:

- `spec.pricing_reference.provider` (e.g. `"openai"` vs. `"anthropic"`)
- `spec.pricing_reference.pricing_version` (e.g. `"openai-2026-04-30"` vs. a newer table)
- `spec.runtime.model` (e.g. `"gpt-4.1-mini"` vs. `"gpt-4.1"`)

`DiffOutcome` also carries the resolved per-1k token rates for each side directly:

| Field | Description |
|-------|-------------|
| `baseline_input_usd_per_1k_tokens` | Input rate from the baseline pricing table entry (or `None` when not found) |
| `baseline_output_usd_per_1k_tokens` | Output rate from the baseline pricing table entry (or `None`) |
| `baseline_cached_input_usd_per_1k_tokens` | Cached-input rate for baseline (or `None` when not set in the table) |
| `candidate_input_usd_per_1k_tokens` | Input rate from the candidate pricing table entry (or `None`) |
| `candidate_output_usd_per_1k_tokens` | Output rate from the candidate pricing table entry (or `None`) |
| `candidate_cached_input_usd_per_1k_tokens` | Cached-input rate for candidate (or `None`) |

These fields are populated by `pricing_entry_for(table, model)` in `flightdeck.ledger` after
`diff_releases` returns and before the `DiffOutcome` is constructed.

`DiffOutcome.pricing_warnings` is a tuple of human-readable strings when the release artifact's
`spec.runtime.model` has **no** matching row in that side's imported pricing table. Warnings are
**diagnostic only** (they do not change `policy`). If ingested events reference a model that
cannot be priced, `compute_rollup` still raises and `compute_diff` surfaces that as before.

**CLI output** — when `pricing_or_model_changed` is `True`, the CLI prints:

```
NOTE: cost delta includes pricing/model assumption changes (pricing reference and/or model differ).
Per-1k token prices: input 0.005000 -> 0.004500, output 0.015000 -> 0.013500
```

The **Per-1k token prices** line is only printed when both input and output rates are present
for both sides. If any rate is `None`, that line is omitted.

When `pricing_warnings` is non-empty, the CLI also prints one **`WARNING:`** line per string
before the `NOTE:` / per-1k lines.

**HTTP API** — `/v1/diff` includes a `pricing.prices` object alongside the existing
`pricing_or_model_changed` flag and a `pricing.warnings` string array (empty when both models
resolve to a table row):

```json
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
  "warnings": []
}
```

`pricing.prices` is always present in the response (not gated on `pricing_or_model_changed`).
Fields are `null` when the rate is not set in the pricing table.

**Web UI** — the `DiffPage` shows `pricing.warnings` as a warning list when non-empty, then the
`fd-alert--warn` banner for `pricing_or_model_changed` when applicable, and the per-1k input/output price deltas
(baseline → candidate) when all four rates are present. See [web-ui.md § DiffPage](web-ui.md).

This is an informational signal — the diff still computes and the policy still evaluates; cost
deltas may reflect pricing assumption changes in addition to actual usage changes.

Cross-provider diffs (e.g. OpenAI baseline vs. Anthropic candidate) are supported as long as
separate pricing tables for each provider/version are imported. Each side is priced against its
own table independently before deltas are computed.

### Rollup semantics

`ledger.compute_rollup` aggregates a list of `RunEvent` objects into a `Rollup`:

| Field | How it is computed |
|-------|--------------------|
| `runs` | Total number of events in the window |
| `cost_per_run_usd` | Average of `estimate_cost_usd(event, pricing_table)` across all events |
| `latency_ms_avg` | Average of `metrics.latency_ms` across events **where latency is present**; `None` when no event has latency data |
| `error_rate` | Fraction of events where `metrics.success == False` |

**All events in the query window count** — including `type: run_start` events. The
`run_id` is the deduplicated key; if an agent emits both `run_start` and `run_end` for
the same logical run, **both** are stored and counted unless they share the same `run_id`.
Best practice is to ingest only `run_end` (the default `type`) when a single-event
model is used, or use distinct `run_id` values when emitting both start and end events.

`latency_ms_avg` is `None` (not zero) when the window has no events with latency data.
Policy's `max_latency_ms` check is **skipped** when `latency_ms_avg` is `None`.

`delta_cost_per_run_pct` in `DiffResult` is `None` when `baseline.cost_per_run_usd == 0`
(division by zero guard). Similarly, `delta_latency_ms_avg` is `None` when either side
has no latency data.

---

## `promote_release` / `rollback_release`

Both delegate to the private `_evaluate_promotion_or_rollback`:

```python
promote_release(
    *,
    cfg, storage,
    release_id: str,
    environment: str,
    window: str,
    reason: str,     # non-empty required
    actor: str,
) -> ActionOutcome
```

### Steps

1. Validate `reason` is non-empty (required for the audit record).
2. Load the target release artifact.
3. Look up the current promoted release for `(agent_id, environment)`.
4. **First promotion path:** if no current promoted release exists and action is
   `"promote"`, skip diff evaluation and construct a passing `PolicyResult`.
5. **Normal path:** load pricing tables for both the current promoted release (baseline)
   and the target release (candidate), query run events, compute a diff, and evaluate
   policy.
6. Write a `PromotionRecord` to `release_actions` (audit ledger) regardless of policy
   outcome.
7. If policy passes, call `storage.commit_promotion` to atomically write the action
   record and update `promoted_releases`. Set `promoted_pointer_changed = True`.
8. If policy fails, the record is written but the pointer is not updated. Return
   `promoted_pointer_changed = False`.

### Rollback vs. promote

The only semantic difference is the `action` field (`"rollback"` vs. `"promote"`).
Both are policy-gated, both write to the audit ledger, and both update the promoted
pointer on success. A rollback *to* a release that is not registered raises
`OperationError`.

### `ActionOutcome` fields

| Field | Description |
|-------|-------------|
| `action_id` | `act_` + 12 random hex chars |
| `action` | `"promote"` or `"rollback"` |
| `release_id` | The release being promoted/rolled back to |
| `agent_id` | Derived from the release artifact |
| `environment` | As passed |
| `baseline_release_id` | The previously promoted release (or `None` for first promotion) |
| `promoted_pointer_changed` | `True` if the pointer was updated (policy passed) |
| `policy` | `PolicyResult` with `passed`, `reasons`, `evaluated_at` |

---

## Policy system

### `Policy` model

```python
class Policy(BaseModel):
    policy_id: str = "default"

    # Absolute limits on candidate metrics
    max_cost_per_run_usd: float | None = None
    max_latency_ms: int | None = None
    max_error_rate: float | None = None

    # Sample size thresholds for confidence
    min_candidate_runs: int | None = None
    min_baseline_runs: int | None = None
    min_low_runs: int | None = None

    # Require HIGH confidence before promotion
    require_high_diff_confidence: bool = True
```

All `max_*` fields default to `None` (disabled). Set them to enable the constraint.
All `min_*` fields default to `None` (defer to `WorkspaceConfig.diff` defaults).

### Setting the active policy

`active_policy` is a single-row table keyed on `policy_id`. `policy set` uses an
`INSERT … ON CONFLICT(policy_id) DO UPDATE` upsert, so calling it repeatedly with
the same `policy_id` always overwrites in place. Changing `policy_id` between calls
creates a second row; `get_active_policy` resolves ambiguity by returning the row
with the most recent `updated_at`.

```bash
flightdeck policy set examples/quickstart/policy.yaml
flightdeck policy show
```

Example `policy.yaml`:

```yaml
policy_id: prod-v1
max_cost_per_run_usd: 0.005
max_error_rate: 0.02
require_high_diff_confidence: true
min_candidate_runs: 200
min_baseline_runs: 200
min_low_runs: 20
```

JSON Schema: [`schemas/v1/policy.schema.json`](../schemas/v1/policy.schema.json).

### Confidence tiers

Confidence is determined by comparing event counts against resolved thresholds:

| Label | Condition |
|-------|-----------|
| `HIGH` | `baseline_runs >= min_baseline_runs` AND `candidate_runs >= min_candidate_runs` |
| `LOW` | `baseline_runs < min_low_runs` OR `candidate_runs < min_low_runs` |
| `MEDIUM` | Otherwise (at least one side missed its target but neither is below the floor) |

Thresholds are resolved from the active policy first; if the policy field is `None`, the
`WorkspaceConfig.diff` default is used (typically `500` / `500` / `50`).

**Zero overrides:** setting a threshold to `0` in the policy means "no minimum
required" — including empty event windows. All three set to `0` lets an empty window
reach HIGH confidence. This is intentional for unit tests and staging environments
where run data is sparse.

```yaml
# policy for staging: allow promotion with any sample size
min_candidate_runs: 0
min_baseline_runs: 0
min_low_runs: 0
require_high_diff_confidence: false
```

**`confidence_reason` format:** when confidence is not `HIGH`, a human-readable explanation is
set on `DiffResult.confidence_reason`. It is a semicolon-joined string of the applicable parts:

- `"candidate sample < {N} runs"` — candidate count is below `min_candidate_runs`
- `"baseline sample < {N} runs"` — baseline count is below `min_baseline_runs`
- `"LOW floor is {N} runs"` — either side is below `min_low_runs`
- Falls back to `"insufficient sample size"` when none of the above apply (should not occur in practice).

The same reason string is appended to the policy failure message when
`require_high_diff_confidence` blocks promotion, e.g.:
`"diff confidence is MEDIUM (candidate sample < 500 runs); promotion requires HIGH"`.

### Constraint evaluation: all constraints are checked

`evaluate_policy` checks **all** enabled constraints in order and accumulates every failure
reason before returning. A single promotion attempt can fail multiple constraints simultaneously:

1. `max_cost_per_run_usd` — candidate average cost must not exceed the limit.
2. `max_latency_ms` — candidate average latency must not exceed the limit. Skipped when candidate has no latency data.
3. `max_error_rate` — candidate error rate must not exceed the limit.
4. `require_high_diff_confidence` — when `True`, the diff must reach HIGH confidence.

Each failed constraint appends one entry to `policy.reasons`. An empty `reasons` list means
the policy passed (`passed = True`). This means **multiple reasons can appear** when several
constraints fail at once — e.g. cost and error rate both over-limit produce two entries.

### Promotion blocked by policy

When policy fails, the promotion/rollback attempt is **recorded in the audit ledger**
(the intent is captured) but the promoted pointer is **not** updated.

- **CLI:** exits with a non-zero code and prints the policy failure reasons.
- **HTTP API:** returns **HTTP 409 Conflict** with a structured `detail` body containing
  `message` and the full `outcome` object (including `promoted_pointer_changed: false` and
  `policy.passed: false`). See [HTTP API reference](http-api.md#post-v1promote) for the
  exact response shape.
- **SDK (`post_promote` / `post_rollback`):** raises `httpx.HTTPStatusError` with
  `response.status_code == 409`. The full `detail` body is accessible via
  `e.response.json()["detail"]`.

---

## `flightdeck doctor`

`flightdeck doctor` runs three read-only integrity checks against the local ledger. It
calls `Storage.migrate()` at start (idempotent), so it also applies any pending schema
migrations.

| Check name | What it verifies |
|------------|-----------------|
| `schema_migrations` | All migration versions 1..`LATEST_SCHEMA_MIGRATION_VERSION` are present in `schema_migrations` |
| `promoted_pointer:<agent_id>:<environment>` | Every `release_id` in `promoted_releases` has a matching row in `releases` |
| `audit_seq` | `release_actions.audit_seq` is contiguous from 1..max with no NULLs, gaps, or duplicates |

Exit behavior: all checks pass → `0`; any failure → prints the failed check to stderr and
exits non-zero (`click.ClickException`).

```
ok    schema_migrations: applied=[1, 2, 3, 4] expected 1..4
ok    promoted_pointer:agent_support:production: release_id=rel_abc123 ok
ok    audit_seq: contiguous 1..4 (4 row(s))
Doctor: 3 check(s), all passed.
```

`audit_seq` is the append-only ledger's tamper-detection signal: every promote/rollback
increments it by 1 inside a `BEGIN IMMEDIATE` transaction. A gap in the sequence indicates
either a manual database edit or a partial write that was rolled back without cleanup.

---

## `list_timeline`

```python
list_timeline(
    *,
    storage: Storage,
    agent_id: str | None = None,
    environment: str | None = None,
    action_limit: int = 50,
) -> TimelineOutcome
```

Returns `releases`, `promoted`, and `actions` in a single call. Used by all three read
endpoints (`GET /v1/releases`, `GET /v1/promoted`, `GET /v1/actions`) and internally by
`flightdeck release history`.

---

## SQLite storage schema

The operations layer reads and writes seven tables (via `src/flightdeck/storage.py`):

| Table | Purpose |
|-------|---------|
| `releases` | Immutable release records keyed by `release_id` |
| `pricing_tables` | Pricing data keyed by `(provider, pricing_version)` |
| `pricing_import_audit` | Append-only log of every `pricing import` operation (insert or replace) |
| `run_events` | Ingested runtime evidence indexed by `(release_id, timestamp)` |
| `active_policy` | Single-row table holding the active `Policy` JSON |
| `promoted_releases` | Current promoted pointer per `(agent_id, environment)` |
| `release_actions` | Append-only audit ledger; `audit_seq` is monotonically increasing |

`Storage.migrate()` runs forward-only numbered migrations. `flightdeck doctor` verifies
that migrations are applied through `LATEST_SCHEMA_MIGRATION_VERSION` and that
`audit_seq` has no gaps.

### `run_events` column layout

The `run_events` table stores six indexed columns extracted from each `RunEvent` (used for
filtering in diff and promote/rollback queries) plus the full serialized event:

| Column | Source | Notes |
|--------|--------|-------|
| `run_id` | `RunEvent.run_id` | PRIMARY KEY; duplicate inserts are silently skipped (idempotent ingestion) |
| `release_id` | `RunEvent.release_id` | Covered by the `(release_id, timestamp)` index added in migration v2 |
| `agent_id` | `RunEvent.agent_id` | Stored for direct inspection; not used as a WHERE clause in current query paths |
| `tenant_id` | `RunEvent.tenant_id` | Used as a filter in `query_runs` (optional `--tenant` flag on `release diff`) |
| `task_id` | `RunEvent.task_id` | Used as a filter in `query_runs` (optional `--task` flag on `release diff`) |
| `environment` | `RunEvent.environment` | Used as a filter in all diff and promote/rollback queries |
| `timestamp` | `RunEvent.timestamp` | ISO-8601 string; used for time-window filtering (`since ≤ timestamp < until`) |
| `event_json` | Full `RunEvent` serialized to JSON | Deserialized into `RunEvent` objects by `query_runs` before returning |

Fields that are stored inside `event_json` but **not** in top-level columns — and therefore
not filterable in diff queries — include `workspace_id`, `labels`, `request`, and all
`usage.*` fields. The `usage` data is read from `event_json` during cost computation in `compute_rollup`.

### Storage connection settings

Every connection is configured with four pragmas before any statement runs:

| Pragma | Value | Effect |
|--------|-------|--------|
| `foreign_keys` | `ON` | Referential integrity enforcement |
| `journal_mode` | `WAL` | Write-ahead logging; multiple readers can co-exist with a writer |
| `synchronous` | `NORMAL` | Durable enough for power-loss safety without `FULL` fsync overhead |
| `busy_timeout` | `5000` | Wait up to 5 s for a lock before returning `SQLITE_BUSY` |

Write operations that must be atomic (promote/rollback, pricing import) use
`BEGIN IMMEDIATE` transactions, which acquire the write lock upfront and prevent
`SQLITE_BUSY` races between concurrent writers.

### Idempotent run event ingestion

`insert_run_events` inserts rows one at a time and **silently ignores**
`sqlite3.IntegrityError` on `run_id` PRIMARY KEY conflicts. This means:

- Re-ingesting a JSONL file is safe; duplicate events are skipped.
- The return value is the number of **newly inserted** rows (not the total count
  in the input).
- Events are not batched in a single transaction, so a partial failure leaves
  already-inserted rows in place. Re-running the ingest picks up where it left
  off because duplicates are skipped.

### Schema migrations

Migrations are numbered and forward-only; they are never reversed.

| Version | Change |
|---------|--------|
| 1 | Initial schema (all base tables via `CREATE TABLE IF NOT EXISTS`) |
| 2 | `CREATE INDEX … ON run_events(release_id, timestamp)` — speeds up diff/query |
| 3 | `ALTER TABLE release_actions ADD COLUMN audit_seq INTEGER`; backfill existing rows; add unique index |

New migrations must increment `LATEST_SCHEMA_MIGRATION_VERSION` in `storage.py` and add a
corresponding check in `test_schemas.py` (or `test_doctor.py`).

---

## Common errors and remedies

| Error | Cause | Fix |
|-------|-------|-----|
| `Unknown baseline release: rel_...` | Baseline release ID not registered | `flightdeck release register <path>` |
| `Unknown candidate release: rel_...` | Candidate release ID not registered | `flightdeck release register <path>` |
| `Missing pricing table for baseline openai/2024-02` | Pricing not imported for baseline provider/version | `flightdeck pricing import <path>` |
| `Missing pricing table for candidate openai/2024-02` | Pricing not imported for candidate provider/version | `flightdeck pricing import <path>` |
| `Missing pricing table for rollback target openai/2024-02` | Pricing not imported for promote/rollback target | `flightdeck pricing import <path>` |
| `Missing pricing table for promoted_baseline openai/2024-02` | Pricing for the currently-promoted baseline is not present | Import the missing table with `flightdeck pricing import <path>` |
| `Cross-agent diff is not allowed` | Releases belong to different agents | Use releases from the same `agent_id` |
| `Each side of the diff must have a single consistent agent_id among run events` | Ingested events for that release contain mixed `agent_id` values | Verify all `RunEvent` records use the correct `agent_id` matching the release artifact; re-ingest corrected events |
| `Pricing table missing model entry` | Pricing table does not list the model used in the release | Add the model to the pricing YAML and reimport with `--replace` |
| `Reason is required for promote/rollback actions` | Empty `--reason` flag | Provide a non-empty `--reason` |
| `No promoted release exists for this agent/environment; nothing to roll back to` | Trying to roll back with no baseline | Promote a release first |
| `Promoted baseline release is missing: rel_...` | A promoted pointer exists but the referenced release record is gone (e.g. manual DB edit) | Restore from backup; then re-register the release if the artifact is available and promote it to reset the pointer |
| `Workspace config not found: flightdeck.yaml` | Missing `flightdeck.yaml` | `flightdeck init` |

---

## Operational runbook

### SQLite `SQLITE_BUSY` errors

FlightDeck uses WAL mode with a 5-second busy timeout (see [Storage connection settings](#storage-connection-settings)). `SQLITE_BUSY` occurs when a write lock is held longer than 5 seconds.

**Typical causes:**

- Another `flightdeck serve` or CLI command is running a long `BEGIN IMMEDIATE` transaction.
- The database file is on a network filesystem that does not support `LOCK_EX` correctly
  (WAL mode requires byte-range locking).
- OS-level anti-virus or backup software has the file open.

**Remedies:**

1. Ensure only one writer is active at a time (CLI and server share the same DB file).
2. Move `db_path` to a local filesystem if you see persistent locking issues on NFS or SMB.
3. For batch operations that hit the limit, reduce parallelism — FlightDeck is designed for
   single-user local use, not concurrent writers.

### Backup and restore

The full FlightDeck state lives in two places:

- `flightdeck.yaml` — workspace config (safe to version-control; contains no secrets)
- `.flightdeck/flightdeck.db` — SQLite database (gitignored by default)

**Backup** (safe copy while the server is not running):

```bash
cp .flightdeck/flightdeck.db .flightdeck/flightdeck.db.bak
```

**Backup with WAL checkpoint** (safe while the server is running; ensures WAL is flushed):

```bash
sqlite3 .flightdeck/flightdeck.db "PRAGMA wal_checkpoint(FULL);"
cp .flightdeck/flightdeck.db .flightdeck/flightdeck.db.bak
```

**Restore:** stop the server, replace `flightdeck.db` with the backup, restart.

```bash
cp .flightdeck/flightdeck.db.bak .flightdeck/flightdeck.db
```

After restore, run `flightdeck doctor` to confirm integrity.

### Interpreting `flightdeck doctor` failures

| Check | Failure message | Meaning | Fix |
|-------|----------------|---------|-----|
| `schema_migrations` | `migrations applied=[1, 2, 3] but expected 1..4` | A newer migration has not run (DB was created by an older version) | Run `flightdeck doctor` again (it calls `migrate()` at start); if it still fails, the DB file may be from a version with a different schema history |
| `promoted_pointer:<agent>:<env>` | `release_id=rel_... not found in releases` | A promoted pointer references a deleted or never-registered release | Re-register the release with the same ID (not supported) or reset the promoted pointer by promoting a known good release |
| `audit_seq` | `gap at seq=5` or `duplicate seq=3` | The `release_actions` table has a missing or duplicate `audit_seq` | Indicates a manual DB edit or incomplete write; restore from backup and reinspect the affected rows with `sqlite3` |

For the `audit_seq` gap case, you can inspect the table directly:

```bash
sqlite3 .flightdeck/flightdeck.db \
  "SELECT audit_seq, action, release_id, created_at FROM release_actions ORDER BY audit_seq;"
```
