# Troubleshooting

This document covers common problems encountered while developing FlightDeck or operating
`flightdeck serve`. For the operational runbook (SQLite busy errors, backup/restore,
interpreting `doctor` failures) see [operations-and-policy.md](operations-and-policy.md).

---

## Developer environment

### `uv sync` or `pip install` fails on CPython 3.10 or earlier

FlightDeck requires **CPython 3.11+** (see `requires-python` in `pyproject.toml` and the
`.python-version` pin for `uv`).

```
ERROR: Package 'flightdeck-ai' requires a different Python: 3.10.x not in '>=3.11'
```

Install a supported CPython (for example `uv python install 3.12`) or from
[python.org](https://www.python.org/downloads/). Confirm the active interpreter:

```bash
python --version
# or
uv python list
```

---

### `flightdeck --help` prints nothing / command not found after `uv sync`

`uv sync` installs an editable package but the console script `flightdeck` is only on `PATH`
inside `uv run` or an activated venv. Use one of:

```bash
# Preferred: prefix all commands with uv run
uv run flightdeck --help

# Alternative: activate the venv first (Unix)
source .venv/bin/activate
flightdeck --help
```

On Windows, activate with `.venv\Scripts\activate` (cmd) or
`.venv\Scripts\Activate.ps1` (PowerShell).

---

### `pytest` fails with `PermissionError` mentioning `pytest-of-...`

This is a Windows temp-dir issue. `tests/conftest.py` redirects `TEMP`/`TMP` to the
repo-local `.tmp/` directory during test runs (created automatically). If the OS temp path
is restricted by group policy or antivirus, set environment variables before running tests:

```powershell
$env:TEMP = (Resolve-Path .tmp).Path
$env:TMP  = $env:TEMP
uv run python -m pytest
```

Set `FLIGHTDECK_USE_SYSTEM_TEMP=1` to force pytest to use the OS default path again.

---

### `ruff check` reports errors after a code change

Run `uv run python -m ruff check --fix src tests` to apply auto-fixable issues. For
remaining errors, read the rule code (e.g. `E501`, `F401`) in the output and fix manually.

Check what ruff version CI uses: `uv run python -m ruff --version` (must match `ruff==0.15.12`
pinned in `pyproject.toml [project.optional-dependencies] dev`).

---

### `flightdeck-quickstart-verify` exits non-zero

This means one of the quickstart CLI subprocesses failed. The error output names the
failing command and its stderr. Common causes:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `FileNotFoundError: flightdeck` | Console script not installed | Run as `uv run flightdeck-quickstart-verify` or activate the venv |
| `Workspace config not found: flightdeck.yaml` | Working directory wrong | Always run from the repo root |
| `Missing pricing table` | Pricing YAML mismatch | The quickstart fixtures include `pricing-baseline.yaml` and `pricing-candidate.yaml`; they must exist under `examples/quickstart/` |
| `git diff --exit-code schemas/` fails after CI | Schema drift | Run `uv run python scripts/generate_schemas.py` and commit `schemas/` |

---

### Schema drift: CI fails on `git diff --exit-code schemas/`

The `schemas/` directory contains committed JSON Schemas generated from the Pydantic models.
If you changed `src/flightdeck/models.py` or `scripts/generate_schemas.py` without
regenerating the schemas, CI will fail this gate.

Fix:

```bash
uv run python scripts/generate_schemas.py
git diff schemas/       # review changes
git add schemas/ && git commit -m "chore(schemas): regenerate"
```

Do not hand-edit files under `schemas/` directly.

---

### Web UI: `git diff --exit-code src/flightdeck/server/static/` fails

If you changed anything under `web/` (TypeScript, CSS, `vite.config.ts`, or
`web/package.json`), you must rebuild the committed static bundle before pushing:

```bash
cd web
npm ci
npm run build
cd ..
git diff --exit-code src/flightdeck/server/static/
```

If the diff is non-empty, commit all changes under `src/flightdeck/server/static/`:

```bash
git add src/flightdeck/server/static/
git commit -m "chore(web): rebuild static bundle"
```

The build also normalizes line endings (via `web/scripts/normalize-static-lf.mjs`), so CRLF
in the output is not expected. If it appears, ensure git's `text=auto` attribute in
`.gitattributes` is respected or re-run the build on Linux/macOS.

---

### Playwright E2E tests fail locally but pass in CI

`npm run test:e2e` (from `web/`) requires a `flightdeck serve` instance **not** to be
running on port 8765, because Playwright starts its own isolated server. If a stale server
is running on that port, stop it first:

```bash
pkill -f "flightdeck serve"   # Unix
```

Also ensure Playwright browsers are installed:

```bash
cd web && npx playwright install chromium
```

---

## CLI and workspace

### `Workspace config not found: flightdeck.yaml`

Almost all CLI commands read `flightdeck.yaml` from the **current working directory**. Run
`flightdeck init` once per workspace to create the file. If you have multiple workspaces,
`cd` into the right directory before running commands. The only command that does not require
the file is `flightdeck init` itself.

---

### `release register` prints a release ID but `release list` shows nothing

Check that you are in the same directory as the `flightdeck.yaml` that was used during
`register`. The `db_path` in `flightdeck.yaml` points to a specific SQLite file
(default: `.flightdeck/flightdeck.db`). Running commands from a different directory uses a
different config (and a different or missing DB).

---

### `flightdeck release diff` returns `OperationError: Missing pricing table`

The diff needs a pricing table matching each release's `spec.pricing_reference`
(`provider` + `pricing_version`). Import the table first:

```bash
flightdeck pricing import pricing-openai-2024-05.yaml
```

If both the baseline and candidate use different pricing references (cross-provider diff),
import **both** tables. Each is stored independently by `(provider, pricing_version)`.

---

### Diff confidence is MEDIUM or LOW with enough data

The confidence label depends on run counts relative to the **active policy thresholds**,
which fall back to the `flightdeck.yaml` diff defaults when not set by a policy.

Check the active policy:

```bash
flightdeck policy show
```

Default thresholds (`flightdeck.yaml`): `min_candidate_runs: 500`, `min_baseline_runs: 500`,
`min_low_runs: 50`. If your event windows are smaller, either set lower thresholds in the
policy or ensure more runs are ingested.

To allow any sample size (e.g. in staging):

```yaml
# policy-staging.yaml
min_candidate_runs: 0
min_baseline_runs: 0
min_low_runs: 0
require_high_diff_confidence: false
```

---

### `runs ingest` reports `Inserted 0 events` on a non-empty file

The most likely cause is that all `run_id` values in the file already exist in storage —
re-ingesting the same file is safe and idempotent. The count reflects **newly** inserted
rows only.

If the file was not previously ingested, check that:

1. The file is valid JSONL (each line is a complete JSON object) or a JSON array.
2. The `run_id` values in the file are unique; if you generated them programmatically,
   ensure no collision across runs.
3. The `release_id` placeholder (`__BASELINE_RELEASE_ID__`) has been substituted with
   the real ID from `release register`.

---

### Policy blocked promotion but I do not know which constraint failed

The policy failure reasons are printed to stdout and written to the audit ledger. Check the
last history entry:

```bash
flightdeck release history --agent <agent_id> --env <environment>
```

The indented lines below the action show each failed constraint. The same reasons appear in
the HTTP 409 response body (`detail.outcome.policy.reasons`) and in `GET /v1/actions`
(`policy_reasons`).

---

## Server (`flightdeck serve`)

### Server starts on a different port and the web UI shows a blank page

The web UI is a single-page app that calls the API relative to `window.location.origin`.
If the server is on port 9000 but the browser is pointing at a stale URL for 8765, open
the correct base URL: `http://127.0.0.1:9000/`.

---

### `POST /v1/promote` returns HTTP 401 or 403

| Status | Meaning | Fix |
|--------|---------|-----|
| 401 | `FLIGHTDECK_LOCAL_API_TOKEN` is set but the request did not include `Authorization: Bearer <token>` | Add the header or set `api_token` in the SDK client |
| 403 | No token is configured but the caller is not a loopback client | Bind the server to `127.0.0.1` (default), or set `FLIGHTDECK_LOCAL_API_TOKEN` and use Bearer auth |

---

### `POST /v1/events` succeeds but data does not appear in the diff

`POST /v1/events` accepts events **without** a token gate. Check that:

1. The `release_id` in the events matches the value returned by `release register` (not a
   placeholder like `__BASELINE_RELEASE_ID__`).
2. The `environment` in the events matches the `--env` flag used in `release diff`
   (defaults to `WorkspaceConfig.default_environment`, typically `"local"`).
3. The `timestamp` values fall within the diff window. Events outside the `since`/`until`
   bounds are excluded from rollups.

Run `release diff` with the same `--window` and `--env` and inspect `samples.baseline_runs`
and `samples.candidate_runs` in the output.

---

### Web UI shows "Could not load server security mode"

`SecurityStatusBar` fetches `/health` on mount. This error means the browser could not
reach the server. Check that `flightdeck serve` is running and that the port matches.

In development, ensure the Vite dev proxy target matches the server:

```bash
# web/.env.local
VITE_DEV_PROXY_TARGET=http://127.0.0.1:8765
```

---

### `flightdeck doctor` reports `audit_seq` gap

An `audit_seq` gap means the `release_actions` sequence is not contiguous — a write was
rolled back or the table was edited directly. This should not occur in normal operation.

```bash
# Inspect the sequence
sqlite3 .flightdeck/flightdeck.db \
  "SELECT audit_seq, action, release_id, created_at FROM release_actions ORDER BY audit_seq;"
```

If the gap is confirmed, restore from a known-good backup and re-run the operations that
were lost. See [operations-and-policy.md § Backup and restore](operations-and-policy.md#backup-and-restore).

---

## SDK

### `ingest_run_events` raises `httpx.HTTPStatusError` with status 400

The server rejected at least one event. Check the error detail:

```python
except httpx.HTTPStatusError as e:
    print(e.response.json())
```

Common causes:

| Error detail | Fix |
|--------------|-----|
| `Unsupported api_version for POST /v1/events: ...` | Ensure `RunEvent.api_version == "v1"` (the default) |
| `Invalid RunEvent: field required` | A required field (`agent_id`, `release_id`, `run_id`, `tenant_id`, `task_id`, `timestamp`, `environment`, `usage`) is missing |
| `Invalid RunEvent: value is not a valid integer` | `input_tokens`, `output_tokens`, or `cached_input_tokens` must be non-negative integers, not floats |

---

### `post_promote` always returns HTTP 409

Check whether the policy is blocking promotion on every attempt:

```python
except httpx.HTTPStatusError as e:
    if e.response.status_code == 409:
        print(e.response.json()["detail"]["outcome"]["policy"]["reasons"])
```

The reasons explain which constraints failed. Adjust the policy, collect more run evidence,
or use a wider diff window. Every blocked attempt is still recorded in the audit ledger.

---

### SDK retries do not fire on 4xx responses

`max_retries` only applies to `httpx.RequestError` (network-level failures like connection
refused or DNS resolution errors). HTTP 4xx and 5xx responses raise `httpx.HTTPStatusError`
immediately without retrying — these are application-level errors, not transient network
problems.

---

## See also

- [operations-and-policy.md](operations-and-policy.md) — operational runbook for SQLite busy errors,
  backup/restore, and `doctor` failure interpretation
- [http-api.md](http-api.md) — full HTTP API reference including error response shapes
- [cli.md](cli.md) — CLI exit codes and flag reference
- [DEVELOPMENT.md](../DEVELOPMENT.md) — setup, verify commands, and web UI rebuild instructions
