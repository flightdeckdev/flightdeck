# FlightDeck CLI Reference

`flightdeck` is the primary interface for AI release governance: registering releases,
ingesting runtime evidence, computing diffs, and promoting or rolling back with policy gates.

All commands require a `flightdeck.yaml` in the current working directory (except `init`).
Run `flightdeck init` to create one.

## Top-level flags

```
flightdeck [--version] [--help]
```

`--version` prints the installed version and exits.

---

## `flightdeck init`

Create a `flightdeck.yaml` workspace config in the current directory.

```bash
flightdeck init
flightdeck init --path /path/to/flightdeck.yaml
```

| Flag | Default | Description |
|------|---------|-------------|
| `--path` | `flightdeck.yaml` | Output file path |

Exits with an error if the file already exists. See [release-artifact.md](release-artifact.md)
for the full `flightdeck.yaml` field reference.

---

## `flightdeck doctor`

Run read-only integrity checks on the local SQLite ledger.

```bash
flightdeck doctor
```

Checks:

| Check | What it verifies |
|-------|-----------------|
| `schema_migrations` | Migrations 1..`LATEST_SCHEMA_MIGRATION_VERSION` are recorded |
| `promoted_pointer:<agent>:<env>` | Every promoted `release_id` exists in `releases` |
| `audit_seq` | `release_actions.audit_seq` is contiguous 1..max with no gaps |

Exit codes: `0` all pass; `1` any failure.

Example output:
```
ok    schema_migrations: applied=[1, 2, 3] expected 1..3
ok    promoted_pointer:agent_support:production: release_id=rel_abc123 ok
ok    audit_seq: contiguous 1..4 (4 row(s))
Doctor: 3 check(s), all passed.
```

Also runs `Storage.migrate()` (idempotent), so it applies any pending schema migrations
as a side effect.

See [operations-and-policy.md § flightdeck doctor](operations-and-policy.md#flightdeck-doctor)
for details on what each check catches.

---

## `flightdeck serve`

Start the local HTTP service (web UI + JSON API).

```bash
flightdeck serve
flightdeck serve --port 9000
flightdeck serve --host 0.0.0.0   # warns about non-loopback exposure
flightdeck serve --reload          # auto-reload on source changes (dev only)
```

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8765` | TCP port |
| `--reload` | off | Enable uvicorn hot reload |

Binding to a non-loopback host prints a warning to stderr. Use
`FLIGHTDECK_LOCAL_API_TOKEN` to enable Bearer-token auth for mutation routes when
serving beyond loopback:

```bash
export FLIGHTDECK_LOCAL_API_TOKEN="$(openssl rand -hex 32)"
flightdeck serve --host 0.0.0.0
```

The server exposes the web UI at `/`, the JSON API under `/v1/`, and interactive
Swagger docs at `/docs`. See [http-api.md](http-api.md) for the full API reference.

---

## `flightdeck release`

Group of commands for working with release artifacts.

### `release register`

Register an immutable release artifact (a bundle directory or single `release.yaml`).

```bash
flightdeck release register ./my-release-dir
flightdeck release register ./my-release-dir/release.yaml
flightdeck release register ./my-release-dir --env staging
```

| Argument / Flag | Required | Description |
|----------------|----------|-------------|
| `PATH` | yes | Bundle directory (containing `release.yaml`) or path to a single `release.yaml` |
| `--env` | no | Override the environment (defaults to `default_environment` in `flightdeck.yaml`) |

Prints the new `release_id` (e.g. `rel_abc123def456`) to stdout. Capture it for
subsequent commands:

```bash
REL=$(flightdeck release register ./candidate-release)
```

A bundle checksum is computed at registration and stored immutably. Use
`release verify` to confirm the on-disk files have not changed since then.

### `release list`

List all registered releases.

```bash
flightdeck release list
```

Prints tab-separated columns: `release_id`, `agent_id`, `version`, `environment`,
`created_at` (ISO-8601).

### `release show`

Show full details of a registered release as JSON.

```bash
flightdeck release show rel_abc123def456
```

Outputs the `ReleaseRecord` (including `artifact_json`) as pretty-printed JSON.
Exits with an error if the release ID is unknown.

### `release verify`

Verify that on-disk bundle files match the checksum recorded at registration.

```bash
flightdeck release verify rel_abc123def456 --path ./candidate-release
```

| Flag | Required | Description |
|------|----------|-------------|
| `--path` | yes | Bundle directory or single `release.yaml` to hash and compare |

Exit codes:
- `0` — checksum matches
- `1` — normal CLI error (unknown release ID, path not found)
- `2` — checksum mismatch (files differ from registration)

Example output on success:
```
OK: checksum matches for rel_abc123def456
  sha256=e3b0c44298fc1c149afb4c8996fb92427ae41e4649b934ca495991b7852b855
```

Example output on mismatch (printed to stderr, exits 2):
```
CHECKSUM MISMATCH for rel_abc123def456
  stored (DB):       e3b0c44...
  recomputed (disk): aabbccdd...
Disk content differs from registration (files, line endings, or hashing rules).
```

The checksum algorithm is described in [release-artifact.md § Bundle checksum algorithm](release-artifact.md#bundle-checksum-algorithm).

### `release diff`

Compare two registered releases over a time window using ingested run events.

```bash
flightdeck release diff rel_baseline rel_candidate --window 7d
flightdeck release diff rel_baseline rel_candidate --window 24h --env production
flightdeck release diff rel_baseline rel_candidate --window 30m --tenant acme --task resolve_ticket
```

| Argument / Flag | Required | Description |
|----------------|----------|-------------|
| `BASELINE_RELEASE_ID` | yes | Baseline (currently promoted) release |
| `CANDIDATE_RELEASE_ID` | yes | Candidate release to evaluate |
| `--window` | yes | Time window: `{N}d`, `{N}h`, or `{N}m` (e.g. `7d`, `24h`, `30m`) |
| `--env` | no | Filter events by environment (defaults to `default_environment`) |
| `--tenant` | no | Filter events by `tenant_id` |
| `--task` | no | Filter events by `task_id` |

Prints a confidence-labeled report including cost, latency, error-rate deltas, and policy
evaluation result. Example:

```
Window: 7d (2026-04-24T12:00:00+00:00 .. 2026-05-01T12:00:00+00:00)
Filters: env=production tenant=* task=*
Baseline pricing: openai/2024-02 (model=gpt-4o)
Candidate pricing: openai/2024-05 (model=gpt-4o)
NOTE: cost delta includes pricing/model assumption changes (pricing reference and/or model differ).
Samples: baseline=1200 candidate=850
Confidence: HIGH

Estimated model token cost/run (USD): 0.002341 -> 0.002189 (delta -0.000152, -6.50%)
Latency avg (ms): 910.50 -> 875.20 (delta -35.30)
Error rate: 0.0083 -> 0.0071 (delta -0.0012)

Policy: PASS
```

Both releases must belong to the same `agent_id`. Pricing tables for both releases must
be imported before running a diff. See [operations-and-policy.md](operations-and-policy.md)
for detailed semantics.

### `release promote`

Evaluate active policy and promote a release to an environment.

```bash
flightdeck release promote rel_abc123def456 --env production --window 7d --reason "passed staging"
```

| Argument / Flag | Required | Description |
|----------------|----------|-------------|
| `RELEASE_ID` | yes | Release to promote |
| `--env` | yes | Target environment |
| `--window` | yes | Time window for diff evaluation |
| `--reason` | yes | Non-empty rationale written to the audit ledger |

The `actor` is read from `$USER` / `$USERNAME` (falls back to `"unknown"`).

Exit codes:
- `0` — policy passed, release is now the promoted pointer for `(agent_id, environment)`
- `1` — policy failed (audit record is still written; promoted pointer is not updated)

The first promotion for an `(agent_id, environment)` pair is always unconditional — no
diff is computed and no policy is evaluated.

### `release rollback`

Roll back to a prior release. Identical contract to `release promote` but sets
`action = "rollback"` in the audit ledger. A currently promoted release must exist;
rolling back when nothing is promoted returns an error.

```bash
flightdeck release rollback rel_prev789 --env production --window 7d --reason "regression in prod"
```

Flags are identical to `release promote`.

### `release history`

Show the promotion and rollback decision history from the audit ledger.

```bash
flightdeck release history
flightdeck release history --agent agent_support
flightdeck release history --env production
flightdeck release history --agent agent_support --env production
```

| Flag | Description |
|------|-------------|
| `--agent` | Filter by `agent_id` |
| `--env` | Filter by environment |

Prints tab-separated rows: `created_at`, `action`, `PASS`/`FAIL`, `release_id`,
`baseline=<id>`, `actor=<name>`, `reason=<text>`. Policy failure reasons are printed
on indented lines below each row.

---

## `flightdeck pricing`

Group of commands for managing pricing tables (used by `compute_diff` to calculate
`cost_per_run_usd`).

### `pricing import`

Import a pricing table YAML into local storage.

```bash
flightdeck pricing import pricing-openai-2024-05.yaml
flightdeck pricing import pricing-openai-2024-05.yaml --replace --reason "corrected cached rate"
```

| Argument / Flag | Required | Description |
|----------------|----------|-------------|
| `PATH` | yes | Pricing table YAML file |
| `--replace` | no | Replace an existing `(provider, pricing_version)` table |
| `--reason` | conditionally | Required when `--replace` is set; written to the pricing import audit log |

Every import writes a record to the `pricing_import_audit` SQLite table (with
`import_id`, provider, version, action, actor, reason, and checksums of old/new JSON).

See [release-artifact.md § Pricing table YAML format](release-artifact.md#pricing-table-yaml-format)
for the YAML schema.

### `pricing show`

Show a stored pricing table by provider and version.

```bash
flightdeck pricing show --provider openai --version 2024-05
```

| Flag | Required | Description |
|------|----------|-------------|
| `--provider` | yes | Provider name (e.g. `openai`, `anthropic`) |
| `--version` | yes | Pricing version string (e.g. `2024-05`) |

Prints the `PricingTable` as pretty-printed JSON. Exits with an error if the table
is not found.

---

## `flightdeck policy`

Group of commands for managing the active promotion policy.

### `policy set`

Set the active policy from a YAML file.

```bash
flightdeck policy set policy.yaml
```

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | yes | Policy YAML file |

Replaces the active policy (single-row table in SQLite). Example YAML:

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
See [operations-and-policy.md § Policy system](operations-and-policy.md#policy-system) for
full constraint semantics.

### `policy show`

Show the currently active policy.

```bash
flightdeck policy show
```

Prints the active `Policy` as pretty-printed JSON. If no policy has been set, prints the
default policy (`require_high_diff_confidence: true`, all `max_*` and `min_*` fields
`null`).

---

## `flightdeck runs`

Group of commands for ingesting runtime evidence.

### `runs ingest`

Ingest `RunEvent` records from a JSONL or JSON array file into local storage.

```bash
flightdeck runs ingest events.jsonl
flightdeck runs ingest events.json
```

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | yes | JSONL file (one JSON object per line) or JSON array file |

Prints `Inserted N events`. Events with duplicate `run_id` values are silently
skipped (idempotent). An empty input file inserts 0 events without error.

For ingest from Python code, use the SDK's `ingest_run_events` method instead.
Full `RunEvent` field reference: [`schemas/v1/run_event.schema.json`](../schemas/v1/run_event.schema.json).

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | CLI error (bad arguments, missing config, operation error, policy failure) |
| `2` | Checksum mismatch (`release verify` only) |

---

## End-to-end workflow

```bash
# 1. Initialize workspace
flightdeck init

# 2. Import pricing tables for baseline and candidate releases
flightdeck pricing import pricing-openai-2024-02.yaml
flightdeck pricing import pricing-openai-2024-05.yaml

# 3. Set promotion policy
flightdeck policy set policy.yaml

# 4. Register releases
BASELINE=$(flightdeck release register ./baseline-release)
CANDIDATE=$(flightdeck release register ./candidate-release --env production)

# 5. Ingest runtime evidence
flightdeck runs ingest baseline-events.jsonl
flightdeck runs ingest candidate-events.jsonl

# 6. Compute a diff (optional preview step)
flightdeck release diff $BASELINE $CANDIDATE --window 7d --env production

# 7. Promote (evaluates policy; writes audit record)
flightdeck release promote $CANDIDATE --env production --window 7d --reason "all staging checks passed"

# 8. Verify on-disk bundle integrity
flightdeck release verify $CANDIDATE --path ./candidate-release

# 9. Check ledger health
flightdeck doctor
```

For CI automation and programmatic workflows, see the [HTTP API](http-api.md) and
[Python SDK](sdk.md) references.
