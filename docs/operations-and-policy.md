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
4. Parse `window` into a `timedelta`; compute `since = now - delta`, `until = now`.
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

### Cross-provider and cross-model diffs

`compute_diff` supports comparing releases that use different pricing providers, pricing
versions, or model names. Each side is costed independently against its own pricing table,
so the cost delta reflects the combined effect of token usage changes *and* any
pricing/model assumption changes.

When the baseline and candidate differ on any of provider, pricing version, or model name,
`pricing_or_model_changed` is set to `true` in the `DiffOutcome`. This flag propagates to:

- **CLI output** — an explicit note is printed:
  ```
  NOTE: cost delta includes pricing/model assumption changes (pricing reference and/or model differ).
  ```
- **HTTP response** — the `pricing` object in `POST /v1/diff` includes
  `"pricing_or_model_changed": true`, plus the individual `baseline_provider`,
  `baseline_version`, `baseline_model`, `candidate_provider`, `candidate_version`, and
  `candidate_model` fields.
- **Web UI** — `DiffPage` renders an `fd-alert--warn` banner when this flag is `true` (see
  [web-ui.md](web-ui.md#diffpage-websrcpagesdiffpagetsx)).

The `DiffOutcome` pricing fields are:

| Field | Description |
|-------|-------------|
| `baseline_pricing_provider` | Provider from the baseline release's `spec.pricing_reference.provider` |
| `baseline_pricing_version` | Pricing version from the baseline release's `spec.pricing_reference.pricing_version` |
| `baseline_model` | Model from the baseline release's `spec.runtime.model` |
| `candidate_pricing_provider` | Provider from the candidate release |
| `candidate_pricing_version` | Pricing version from the candidate release |
| `candidate_model` | Model from the candidate release |
| `pricing_or_model_changed` | `True` when any of the three fields differ between baseline and candidate |

**Example — cross-provider diff:**
```bash
flightdeck release diff "$BASELINE" "$CANDIDATE" --window 7d
# Baseline pricing: openai/openai-2026-04-30 (model=gpt-4.1-mini)
# Candidate pricing: anthropic/anthropic-2026-04-30 (model=claude-3-sonnet)
# NOTE: cost delta includes pricing/model assumption changes (pricing reference and/or model differ).
```

**Example — cross-model, same provider:**
```bash
# Both releases use provider=openai, pricing_version=openai-2026-04-30
# Baseline model: gpt-4.1-mini, Candidate model: gpt-4.1
# Output shows (model=gpt-4.1-mini) -> (model=gpt-4.1) with the same note.
```

### Important constraint: cross-agent diffs

`compute_diff` checks that both releases have the same `agent_id` in their artifact
spec *before* querying events. This is checked again inside `diff_releases` if run events
from both sides are non-empty.

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

### Constraint evaluation

`ledger.evaluate_policy` checks constraints in order:

1. **`max_cost_per_run_usd`** — candidate average cost must not exceed the limit.
2. **`max_latency_ms`** — candidate average latency must not exceed the limit. **Skipped
   entirely** when `candidate.latency_ms_avg is None` (i.e., no events in the window
   include latency data). Setting `max_latency_ms` with no latency evidence does not
   cause a policy failure.
3. **`max_error_rate`** — candidate error rate must not exceed the limit.
4. **`require_high_diff_confidence`** — when `True`, the diff must reach `HIGH`
   confidence. A `MEDIUM` or `LOW` diff blocks promotion and adds a reason like
   `"diff confidence is MEDIUM (candidate sample < 500 runs); promotion requires HIGH"`.

**Multiple failures accumulate.** All enabled constraints are evaluated independently;
every failed constraint appends its own reason string to `policy.reasons`. A promotion
attempt can therefore produce multiple policy failure reasons in a single response:

```
Policy: FAIL
- candidate cost_per_run_usd 0.006000 exceeds max 0.005000
- candidate error_rate 0.5000 exceeds max 0.1000
```

Each failed constraint appends a human-readable reason to the result. An empty `reasons`
list means the policy passed (`passed = True`).

**Confidence and policy interaction:**

| Confidence | `require_high_diff_confidence=true` | `require_high_diff_confidence=false` |
|------------|-------------------------------------|--------------------------------------|
| `HIGH` | Pass (confidence check) | Pass (confidence check) |
| `MEDIUM` | **Fail** — reason includes "MEDIUM" and "promotion requires HIGH" | Pass (confidence check) |
| `LOW` | **Fail** | Pass (confidence check) |

Note: the first promotion for an agent/environment always succeeds unconditionally,
regardless of confidence or policy constraints, because there is no baseline to diff
against. The `policy.reasons` field for a first-promotion success contains a single
informational message: `"first promotion: no promoted baseline for agent/environment"`.

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
ok    schema_migrations: applied=[1, 2, 3] expected 1..3
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
| `Unknown baseline release: rel_...` | Release not registered | `flightdeck release register <path>` |
| `Missing pricing table for baseline openai/2024-02` | Pricing not imported | `flightdeck pricing import <path>` |
| `Cross-agent diff is not allowed` | Releases belong to different agents | Use releases from the same `agent_id` |
| `Pricing table missing model entry` | Pricing table does not list the model used in the release | Add the model to the pricing YAML and reimport with `--replace` |
| `Reason is required for promote/rollback actions` | Empty `--reason` flag | Provide a non-empty `--reason` |
| `No promoted release exists for this agent/environment; nothing to roll back to` | Trying to roll back with no baseline | Promote a release first |
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
| `schema_migrations` | `migrations applied=[1, 2] but expected 1..3` | A newer migration has not run (DB was created by an older version) | Run `flightdeck doctor` again (it calls `migrate()` at start); if it still fails, the DB file may be from a version with a different schema history |
| `promoted_pointer:<agent>:<env>` | `release_id=rel_... not found in releases` | A promoted pointer references a deleted or never-registered release | Re-register the release with the same ID (not supported) or reset the promoted pointer by promoting a known good release |
| `audit_seq` | `gap at seq=5` or `duplicate seq=3` | The `release_actions` table has a missing or duplicate `audit_seq` | Indicates a manual DB edit or incomplete write; restore from backup and reinspect the affected rows with `sqlite3` |

For the `audit_seq` gap case, you can inspect the table directly:

```bash
sqlite3 .flightdeck/flightdeck.db \
  "SELECT audit_seq, action, release_id, created_at FROM release_actions ORDER BY audit_seq;"
```
