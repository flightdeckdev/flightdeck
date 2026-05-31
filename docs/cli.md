# FlightDeck CLI Reference

This document covers every `flightdeck` command, its flags, arguments, and exit codes.
The CLI is a **stable public contract** from v1.0.0 — flags, exit codes, and command
names will not change in patch or minor releases.

For the on-disk formats the CLI reads and writes see
[release-artifact.md](release-artifact.md). For the HTTP API exposed by `flightdeck
serve` see [http-api.md](http-api.md).

## Global flags

| Flag | Description |
|------|-------------|
| `--version` | Print the installed version and exit |
| `--help` | Print help for any command or subcommand |

Most commands require `flightdeck.yaml` in the working directory (or the default path
`./flightdeck.yaml`). Run `flightdeck init` to create one. **`flightdeck init`** writes the
config, then loads it to migrate the ledger and (by default) import bundled pricing.

**`flightdeck demo`** is an exception: it creates a **temporary** workspace and does not read `./flightdeck.yaml` from your shell cwd.

## Actor resolution

Several commands that write to the audit ledger (`release promote`, `release rollback`,
`pricing import`) record an `actor` value. For CLI commands, `actor` is resolved from
the environment at invocation time:

1. `USER` environment variable (Unix / macOS)
2. `USERNAME` environment variable (Windows)
3. Falls back to `"unknown"` if neither is set

The HTTP API's `POST /v1/promote` and `POST /v1/rollback` accept an explicit `"actor"`
field in the request body (defaults to `"http"` when omitted).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (configuration, operation, policy block, etc.) |
| `2` | Checksum mismatch (`release verify` only) |

---

## `flightdeck init`

Create a default `flightdeck.yaml` workspace config in the current directory. By default
this also **migrates the ledger**, **imports bundled** OpenAI / Anthropic / Google pricing
tables (snapshot **`flightdeck-bundled-2026-05`**), writes **`.flightdeck/pricing-catalog.yaml`**,
and sets **`pricing_catalog_path`** so diffs can show **catalog** rollups without a manual
**`pricing import`**. Use **`--no-bundled-pricing`** for an empty ledger (air-gapped or
custom-only).

```bash
flightdeck init [--path PATH] [--no-bundled-pricing]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `flightdeck.yaml` | Target path for the config file |
| `--no-bundled-pricing` | off | Skip bundled pricing import and catalog; omit `pricing_catalog_path` from the new config |

Fails with exit 1 if the file already exists.

**Example output (default):**
```
Wrote flightdeck.yaml
Bundled pricing snapshot (flightdeck-bundled-2026-05): imported openai, anthropic, google; wrote catalog to .flightdeck/pricing-catalog.yaml
```

The generated file uses defaults except **`pricing_catalog_path`** when bundled pricing is
enabled. Edit `diff.*` thresholds or `db_path` before using in a shared repo. For **PostgreSQL**,
set **`database_url`** to a `postgresql://…` (or `postgres://…`) DSN and install **`psycopg`**
(`uv sync --extra postgres`); **`db_path`** is ignored when **`database_url`** is set.
**`flightdeck doctor --backup`** remains SQLite-only. See [release-artifact.md § Workspace config](release-artifact.md) and [pricing-catalog.md](pricing-catalog.md) (bundled snapshot).

---

## `flightdeck demo`

Run the **examples/quickstart** workflow end-to-end in a **disposable temp directory**: **`init`** → custom **`pricing import`** (both YAMLs) → **`policy set`** → **`release register`** (both bundles) → substitute **`release_id`** placeholders in JSONL → **`runs ingest`** → **`release diff`** → **`release promote`** (baseline under policy) → **`release history`**.

Does **not** require **`flightdeck.yaml`** in the current directory. Fixtures resolve in order: **`--quickstart-root`**, **`FLIGHTDECK_QUICKSTART_ROOT`**, **`examples/quickstart`** relative to a git checkout, then **`flightdeck/_bundled_quickstart`** packaged in the wheel (PyPI installs).

```bash
flightdeck demo [--quickstart-root DIR] [--verify / --no-verify] [--doctor / --no-doctor] [--keep-workspace]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--quickstart-root` | (see above) | Directory containing `policy.yaml`, pricing YAMLs, `*-events.jsonl`, and `baseline-release` / `candidate-release` |
| `--verify` | off | Also run **`release verify`** on the baseline bundle (parity with **`flightdeck-quickstart-verify`**) |
| `--doctor` | off | Also run **`flightdeck doctor`** |
| `--keep-workspace` | off | Keep the temp workspace and print its path |

On success, prints a short confirmation. Exit **0** on success, **1** on failure (same as subprocess failures from underlying CLI steps).

---

## `flightdeck doctor`

Run read-only health checks on the workspace ledger (SQLite file or PostgreSQL when
**`database_url`** is configured).

```bash
flightdeck doctor [--backup PATH]
```

Calls `Storage.migrate()` at start (idempotent). With **`--backup PATH`**, runs an SQLite
online backup of the workspace database to **`PATH`** when the workspace uses SQLite
(**`--backup`** is rejected for PostgreSQL-ledgers; use **`pg_dump`** instead). Parent
directories are created; an existing file is overwritten, then the checks below run.

Without **`--backup`**, only the checks run. In both cases **`migrate()`** runs first.

| Check | What it verifies |
|-------|-----------------|
| `schema_migrations` | All migration versions through `LATEST_SCHEMA_MIGRATION_VERSION` are applied |
| `promoted_pointer:<agent_id>:<env>` | Every `release_id` in `promoted_releases` has a matching row in `releases` |
| `audit_seq` | `release_actions.audit_seq` is contiguous from 1 to max with no NULLs, gaps, or duplicates |

Output format:
```
ok    schema_migrations: applied=[1, 2, 3, 4] expected 1..4
ok    promoted_pointer:agent_support:production: release_id=rel_abc123 ok
ok    audit_seq: contiguous 1..4 (4 row(s))
Doctor: 3 check(s), all passed.
```

Failed checks print to stderr and exit 1. Passing exits 0.

---

## `flightdeck serve`

Start the local FlightDeck HTTP service.

```bash
flightdeck serve [--host HOST] [--port PORT] [--reload] [--sqlite-lock-timeout SECONDS] [--retry-sqlite-lock / --no-retry-sqlite-lock]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address. Non-loopback addresses print a security warning |
| `--port` | `8765` | Bind port |
| `--reload` | off | Hot-reload on source changes (development only) |
| `--sqlite-lock-timeout` | `30` | Seconds to retry SQLite `database is locked` / busy errors on ledger statements (`0` disables timed retries) |
| `--retry-sqlite-lock` | on | Retry locked/busy SQLite executes until the timeout elapses |

The server exposes `/v1/*` JSON routes. See [http-api.md](http-api.md) for full route
documentation.

**Authentication:** set `FLIGHTDECK_LOCAL_API_TOKEN` to require a Bearer token for
ledger writes and for **`GET /v1/*`** read APIs. See
[http-api.md § Authentication](http-api.md).

```bash
export FLIGHTDECK_LOCAL_API_TOKEN="$(openssl rand -hex 32)"
flightdeck serve
```

---

## `flightdeck release`

Subgroup for managing release artifacts.

### `flightdeck release register`

Register an immutable release artifact and print the assigned `release_id`.

```bash
flightdeck release register PATH [--env ENV]
```

| Argument / Option | Description |
|-------------------|-------------|
| `PATH` | Path to a `release.yaml` file or a bundle directory containing one |
| `--env` | Override the environment label for this registration (default: `WorkspaceConfig.default_environment`) |

Prints the new `release_id` (e.g. `rel_abc123def456`) to stdout on success. Use command
substitution to capture it:

```bash
RELEASE_ID=$(flightdeck release register ./candidate-release --env production)
echo $RELEASE_ID
```

The checksum is computed at registration time and stored alongside the artifact JSON.
Use `release verify` later to confirm the on-disk files have not changed.

### `flightdeck release list`

List all registered releases.

```bash
flightdeck release list
```

Output is tab-separated: `release_id`, `agent_id`, `version`, `environment`,
`created_at`. Ordered by creation time (newest first).

### `flightdeck release show`

Print a registered release record as JSON.

```bash
flightdeck release show RELEASE_ID
```

Outputs the full `ReleaseRecord` including `artifact_json` (the parsed `release.yaml`
content) and the stored checksum.

### `flightdeck release verify`

Verify that an on-disk bundle matches the checksum stored at registration.

```bash
flightdeck release verify RELEASE_ID --path BUNDLE_PATH
```

| Argument / Option | Description |
|-------------------|-------------|
| `RELEASE_ID` | The release to verify against |
| `--path` | Bundle directory or single `release.yaml` to recompute checksum from (required) |

**Exit codes:**
- `0` — checksums match
- `1` — release not found or config error
- `2` — checksum mismatch (files changed since registration)

```bash
flightdeck release verify rel_abc123 --path ./candidate-release
# OK: checksum matches for rel_abc123
#   sha256=e3b0c44298fc1c149afb...

# On mismatch: exit code 2 with detail to stderr
```

### `flightdeck release diff`

Compare two registered releases over a time window and print a confidence-labeled
safety diff.

```bash
flightdeck release diff BASELINE_ID CANDIDATE_ID --window WINDOW [OPTIONS]
```

| Argument / Option | Description |
|-------------------|-------------|
| `BASELINE_ID` | Baseline release ID |
| `CANDIDATE_ID` | Candidate release ID |
| `--window` | **Required.** Time window: `7d`, `24h`, `30m`, etc. |
| `--env` | Filter events by environment (default: `WorkspaceConfig.default_environment`) |
| `--tenant` | Filter events by `tenant_id` |
| `--task` | Filter events by `task_id` |
| `--fail-on-policy` | After printing the diff, exit **1** when the active policy does not pass (for CI gates). |
| `--output` | `text` (default) or `json`. **`json`**: same JSON object as **`POST /v1/diff`** (stable keys for `jq` / CI parsers). With **`--fail-on-policy`**, JSON is still printed to stdout before exit **1**. |

Both releases must have the same `agent_id`. Cross-agent diffs are rejected with exit 1.

**Exit codes:** invalid input, missing pricing, or other `OperationError` → non-zero. With **`--fail-on-policy`**, a computed diff whose policy result is **FAIL** also exits **1** (after the usual stdout).

When a release's resolved model has **no row** in its pricing table, the diff still completes
(if rollups do not need that rate for ingested events), and the CLI prints **`WARNING:`** lines
and JSON includes **`pricing.warnings`** — diagnostic only; policy is unchanged.

The diff is a **read-only computation** — it does not write to the audit ledger or update
any promoted pointers.

**Example output:**
```
Window: 7d (2026-04-24T12:00:00+00:00 .. 2026-05-01T12:00:00+00:00)
Filters: env=production tenant=* task=*
Baseline pricing: openai/2024-02 (model=gpt-4o)
Candidate pricing: openai/2024-05 (model=gpt-4o)
Samples: baseline=1200 candidate=850
Confidence: HIGH

Estimated model token cost/run (USD): 0.002341 -> 0.002189 (delta -0.000152, -6.50%)
Latency avg (ms): 910.50 -> 875.20 (delta -35.30)
Error rate: 0.0083 -> 0.0071 (delta -0.0012)

Policy: PASS
```

When pricing or model changes between baseline and candidate, an additional note is
printed:
```
NOTE: cost delta includes pricing/model assumption changes (pricing reference and/or model differ).
Per-1k token prices: input 0.005000 -> 0.004500, output 0.015000 -> 0.013500
```

The **Per-1k token prices** line shows the resolved table entry for each side’s model (input and output USD per 1k tokens), so you can separate **tariff moves** from **token volume** changes in the cost delta.

See [operations-and-policy.md](operations-and-policy.md) for the cost calculation and
confidence algorithm.

### `flightdeck release promote`

Evaluate active policy and promote a release to an environment.

```bash
flightdeck release promote RELEASE_ID --env ENV --window WINDOW --reason REASON
```

| Argument / Option | Description |
|-------------------|-------------|
| `RELEASE_ID` | Release to promote |
| `--env` | **Required.** Target environment |
| `--window` | **Required.** Evidence window used for policy evaluation |
| `--reason` | **Required.** Rationale written to the audit ledger (non-empty) |

The currently promoted release for `(agent_id, environment)` becomes the baseline for
the diff. If no release is currently promoted, the first promotion skips policy
evaluation and succeeds unconditionally.

If policy passes, the promoted pointer is updated and the command exits 0. If policy
fails, the **intent is still recorded** in the audit ledger (the `release_actions` row
is written) but the pointer is not updated and the command exits 1.

```
Promoted rel_abc123 for agent_support/production
Policy: PASS
```

Policy failure output:
```
Policy: FAIL
- candidate cost_per_run_usd 0.006000 exceeds max 0.005000
Error: Promotion blocked by policy
```

When **`promotion_requires_approval: true`** in `flightdeck.yaml`, use **`flightdeck release promote-request`**
and **`flightdeck release promote-confirm`** instead of a direct `promote` (see [http-api.md](http-api.md)).

### `flightdeck release promote-request`

Create a pending promotion after policy evaluation (requires `promotion_requires_approval: true`).

```bash
flightdeck release promote-request RELEASE_ID --env ENV --window WINDOW --reason REASON
```

On success prints `request_id=…` and policy JSON. If policy would block promotion, exits 1
and does **not** create a pending row.

### `flightdeck release promote-confirm`

Apply a pending request from `promote-request`.

```bash
flightdeck release promote-confirm REQUEST_ID --approval-reason REASON
```

### `flightdeck release rollback`

Roll back to a prior release. Same contract as `promote` but records `"rollback"` in
the audit ledger.

```bash
flightdeck release rollback RELEASE_ID --env ENV --window WINDOW --reason REASON
```

A promoted release must already exist for the agent/environment. Rolling back when
nothing is promoted exits 1.

### `flightdeck release history`

Show the promotion and rollback decision history from the audit ledger.

```bash
flightdeck release history [--agent AGENT_ID] [--env ENV]
```

| Option | Description |
|--------|-------------|
| `--agent` | Filter by `agent_id` |
| `--env` | Filter by environment |

Output is tab-separated per action: `created_at`, `action`, `PASS/FAIL`, `release_id`,
`baseline=<id>`, `actor=<actor>`, `reason=<reason>`. Policy failure reasons are indented
below each action line.

```
2026-05-01T13:00:00+00:00	promote	PASS	rel_abc123	baseline=rel_prev789	actor=ci-bot	reason=passed staging
```

**No record limit:** `release history` returns all matching rows from `release_actions`
(newest first). For scripted access to a bounded window, use `GET /v1/actions` which
accepts a `limit` query parameter (1–500, default 50).

---

## `flightdeck pricing`

Subgroup for managing pricing tables.

### `flightdeck pricing import`

Import a pricing table YAML file into local storage.

```bash
flightdeck pricing import PATH [--replace] [--reason REASON]
```

| Argument / Option | Description |
|-------------------|-------------|
| `PATH` | Path to a pricing table YAML file |
| `--replace` | Replace an existing `(provider, pricing_version)` table. Requires `--reason` |
| `--reason` | Rationale for the import or replacement. Required when using `--replace` |

Without `--replace`, importing when a table for that `(provider, pricing_version)` already
exists exits 1. Every import writes an audit record to `pricing_import_audit`.

```bash
# First import
flightdeck pricing import pricing-openai-2024-05.yaml

# Update an existing table (audit-sensitive)
flightdeck pricing import pricing-openai-2024-05.yaml --replace --reason "corrected cached rate"
```

Pricing table YAML format: see [release-artifact.md § Pricing table YAML format](release-artifact.md).

### `flightdeck pricing show`

Show a previously imported pricing table as JSON.

```bash
flightdeck pricing show --provider PROVIDER --version VERSION
```

Both flags are required. If the table does not exist, exits 1 with an error message.

### `flightdeck pricing check`

Check the age of **`flightdeck-bundled-*`** pricing tables in the ledger. Prints one line
per bundled snapshot with its anchor date and approximate age. Non-bundled tables are
ignored.

```bash
flightdeck pricing check [--max-age-days N] [--fail]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--max-age-days` | `90` | Threshold in days. Tables older than this print `STALE` to stderr (and count toward `--fail`). Tables at or under the limit print `OK`. |
| `--fail` | off | Exit 1 if any bundled table exceeds `--max-age-days`. Useful as a CI gate. |

**Example output:**
```
OK     flightdeck-bundled-2026-05  (~11 days old; max 90)
```

If no `flightdeck-bundled-*` tables are in the ledger (e.g. after `flightdeck init --no-bundled-pricing`),
exits 0 and prints `No flightdeck-bundled-* pricing tables in the ledger.`

Use in CI to surface stale bundled snapshots before they silently affect cost estimates:
```bash
flightdeck pricing check --max-age-days 90 --fail
```

See [pricing-catalog.md](pricing-catalog.md) for the bundled snapshot lifecycle and when
to replace with `flightdeck pricing import`.

---

## `flightdeck policy`

Subgroup for managing the active promotion policy.

### `flightdeck policy set`

Load a policy YAML file and set it as the active policy.

```bash
flightdeck policy set PATH
```

The policy is validated against the `Policy` Pydantic model and stored in the
`active_policy` SQLite table. Only one policy is active at a time; setting a new one
replaces the previous.

Example `policy.yaml`:

```yaml
policy_id: prod-v1
max_cost_per_run_usd: 0.005
max_error_rate: 0.02
max_latency_ms: 2000
require_high_diff_confidence: true
min_candidate_runs: 200
min_baseline_runs: 200
min_low_runs: 20
```

JSON Schema: [`schemas/v1/policy.schema.json`](../schemas/v1/policy.schema.json).

### `flightdeck policy show`

Print the active policy as JSON.

```bash
flightdeck policy show
```

If no policy has been set, prints the default policy (all constraints `null`/disabled,
`require_high_diff_confidence: true`).

---

## `flightdeck runs`

Subgroup for ingesting, listing, and exporting run events.

### `flightdeck runs list`

Print ingested events for a release (newest first), truncated to `--limit`.

```bash
flightdeck runs list RELEASE_ID --window WINDOW [--env ENV] [--tenant …] [--task …] [--trace-id ID] [--session-id ID] [--span-id ID] [--offset N] [--limit N] [--output json]
```

`--trace-id`, `--session-id`, and `--span-id` filter to exact matches on ingested `request.*` fields (same query names as `GET /v1/runs`). **`--offset`** skips that many newest-matching events before applying **`--limit`**.

### `flightdeck runs export`

Write the same filtered slice as `runs list` (newest first) as **JSONL** — one `RunEvent` JSON object per line. Default **`--limit`** is **500** (maximum **500**). If more events match the window and filters, only the first **`--limit`** lines are written and a **`WARNING:`** line is printed to **stderr** with `exported` / `matching` counts.

```bash
flightdeck runs export RELEASE_ID --window WINDOW [-o export.jsonl] [--env ENV] [--tenant …] [--task …] [--trace-id ID] [--session-id ID] [--span-id ID] [--offset N] [--limit N]
```

With **`-o` / `--output`**, writes UTF-8 JSONL to that path; without it, writes to **stdout** (suitable for pipes).

### `flightdeck runs ingest`

Ingest `RunEvent` records from a JSONL or JSON array file.

```bash
flightdeck runs ingest PATH
```

| Argument | Description |
|----------|-------------|
| `PATH` | Path to a `.jsonl` file (one JSON object per line) or a `.json` file containing a JSON array of events |

Events with a duplicate `run_id` are silently skipped (idempotent). The command prints
the number of newly inserted events:

```
Inserted 47 events
```

**Input formats:**

JSONL (one event per line):
```jsonl
{"api_version":"v1","type":"run_end","timestamp":"2026-05-01T12:00:00Z","agent_id":"agent_support","release_id":"rel_abc123",...}
{"api_version":"v1","type":"run_end","timestamp":"2026-05-01T12:01:00Z","agent_id":"agent_support","release_id":"rel_abc123",...}
```

JSON array:
```json
[
  {"api_version":"v1","type":"run_end","timestamp":"2026-05-01T12:00:00Z",...},
  {"api_version":"v1","type":"run_end","timestamp":"2026-05-01T12:01:00Z",...}
]
```

**Edge cases:**

| Scenario | Behavior |
|----------|----------|
| Empty file (0 bytes or whitespace only) | Succeeds with `Inserted 0 events`. Not an error. |
| Malformed JSONL (invalid JSON on any line) | Fails with a non-zero exit code and a parse error message. |
| JSON array file | Parsed as a list of events; each element is validated individually. |
| Duplicate `run_id` | Silently skipped; count reflects only newly inserted rows. Re-ingesting the same file is safe. |

See [http-api.md § POST /v1/events](http-api.md) for the full `RunEvent` field reference.

---

## Typical workflow

```bash
# 1. Initialize workspace
flightdeck init

# 2. Import pricing tables
flightdeck pricing import pricing-openai-2024-05.yaml

# 3. Set promotion policy
flightdeck policy set policy.yaml

# 4. Register releases
BASELINE=$(flightdeck release register ./baseline-release)
CANDIDATE=$(flightdeck release register ./candidate-release)

# 5. Ingest run evidence (substitute placeholder release IDs first)
sed "s/__BASELINE_RELEASE_ID__/${BASELINE}/g" baseline-events.jsonl > /tmp/baseline-ev.jsonl
sed "s/__CANDIDATE_RELEASE_ID__/${CANDIDATE}/g" candidate-events.jsonl > /tmp/candidate-ev.jsonl
flightdeck runs ingest /tmp/baseline-ev.jsonl
flightdeck runs ingest /tmp/candidate-ev.jsonl

# 6. Compare releases
flightdeck release diff "$BASELINE" "$CANDIDATE" --window 7d

# 7. Promote if safe
flightdeck release promote "$BASELINE" --env production --window 7d --reason "initial baseline"

# 8. View history
flightdeck release history --agent agent_support --env production

# 9. Health check
flightdeck doctor
```

The `flightdeck-quickstart-verify` command (or `python -m flightdeck.quickstart_smoke`)
runs this entire workflow end-to-end using the bundled example fixtures in
`examples/quickstart/`.
