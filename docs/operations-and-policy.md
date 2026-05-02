# Operations and Policy

This document explains the core release governance logic: how `flightdeck release diff`,
`promote`, and `rollback` work under the hood, how CLI / HTTP / SDK all converge on the
same code, and how the policy system controls promotion gates.

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

### Important constraint: cross-agent diffs

`compute_diff` checks that both releases have the same `agent_id` in their artifact
spec *before* querying events. This is checked again inside `diff_releases` if run events
from both sides are non-empty.

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
2. **`max_latency_ms`** — candidate average latency must not exceed the limit. Skipped
   if the candidate window has no latency data.
3. **`max_error_rate`** — candidate error rate must not exceed the limit.
4. **`require_high_diff_confidence`** — when `True`, the diff must reach HIGH confidence.

Each failed constraint appends a human-readable reason to the result. An empty `reasons`
list means the policy passed (`passed = True`).

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

The operations layer reads and writes five tables (via `src/flightdeck/storage.py`):

| Table | Purpose |
|-------|---------|
| `releases` | Immutable release records keyed by `release_id` |
| `pricing_tables` | Pricing data keyed by `(provider, pricing_version)` |
| `run_events` | Ingested runtime evidence indexed by `(release_id, timestamp)` |
| `active_policy` | Single-row table holding the active `Policy` JSON |
| `promoted_releases` | Current promoted pointer per `(agent_id, environment)` |
| `release_actions` | Append-only audit ledger; `audit_seq` is monotonically increasing |

`Storage.migrate()` runs forward-only numbered migrations. `flightdeck doctor` verifies
that migrations are applied through `LATEST_SCHEMA_MIGRATION_VERSION` and that
`audit_seq` has no gaps.

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
