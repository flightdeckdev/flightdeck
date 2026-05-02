# Development

## Requirements

- **CPython 3.14.x** only (`requires-python` in **`pyproject.toml`**; **`.python-version`** pins **3.14** for **uv**). CI runs **3.14** on Ubuntu and Windows.
- Git
- **[uv](https://docs.astral.sh/uv/)** (recommended): single tool for venvs, installs, and **`uv run`** ([installation](https://docs.astral.sh/uv/getting-started/installation/)). On Windows you can use `py -3 -m pip install uv` if you do not use the standalone installer.

**Note:** search hits like **`flightdeck-1.0.1.dist-info`** under **`.venv/`** are normal install metadata (**distribution name + version**), not references to another repository.

## Setup (uv — recommended)

From the repository root:

```bash
uv sync --extra dev
```

This creates **`.venv/`** (gitignored), installs **`flightdeck`** editable plus **pytest** and **ruff**, and pins versions from **`uv.lock`**.

Optional extras (telemetry, SDK helpers): e.g. **`uv sync --extra dev --extra telemetry`**.

### Package extras

| Extra | Packages installed | When to use |
|-------|--------------------|-------------|
| `dev` | `pytest`, `ruff` | Development and CI; required to run tests and lint |
| `openai` | `openai>=1.0` | If you want to use the OpenAI Python client alongside the SDK in your own agent code (not required by FlightDeck core) |
| `anthropic` | `anthropic>=0.20` | Same, for the Anthropic Python client |
| `telemetry` | `opentelemetry-api`, `-sdk`, `-exporter-otlp` | Forward-looking OTLP integration; FlightDeck core does **not** import OpenTelemetry at runtime |
| `all` | `openai` + `anthropic` + `telemetry` | All optional packages in one shot |

FlightDeck's core package (`flightdeck-ai`) does not import OpenAI, Anthropic, or OpenTelemetry at runtime. These extras exist so your project can declare a single dependency (`flightdeck-ai[openai]`) and get a compatible version of both without resolving conflicts manually.

**Note on listed core dependencies:** `pyproject.toml` currently lists `sqlalchemy`, `aiosqlite`, and `rich` as direct (non-optional) dependencies, but `src/flightdeck/` does not import any of them — the package uses the standard-library `sqlite3` module and plain `click` output. These entries are carried over from earlier prototypes and are scheduled for removal in a future cleanup release.

## Setup (pip — fallback)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Verify

With **uv**:

```bash
uv sync --frozen --extra dev
uv run python -m ruff check src tests
uv run python -m pytest
uv run flightdeck --help
uv run flightdeck doctor
uv run flightdeck-quickstart-verify
```

With an **activated venv** (pip or after `uv sync`):

```bash
python -m ruff check src tests
python -m pytest
flightdeck --help
flightdeck doctor
flightdeck-quickstart-verify
```

Match **CI**’s CLI smoke: **`flightdeck --help`** must run successfully after changes to the CLI surface.

Full command flags and exit codes: [README.md](https://github.com/flightdeckdev/flightdeck/blob/main/README.md). Cross-platform quickstart parity: **`flightdeck-quickstart-verify`** / **`python -m flightdeck.quickstart_smoke`** (also run in CI). HTTP API reference: **[docs/http-api.md](docs/http-api.md)**. Python SDK: **[docs/sdk.md](docs/sdk.md)**.

### What `flightdeck-quickstart-verify` does

`flightdeck-quickstart-verify` (entry point for `src/flightdeck/quickstart_smoke.py`) runs the full
quickstart workflow end-to-end in an isolated temp directory:

1. `flightdeck init`
2. Import both pricing tables from `examples/quickstart/`
3. `flightdeck policy set`
4. Register baseline and candidate releases — capture the `release_id` printed to stdout
5. Substitute `__BASELINE_RELEASE_ID__` / `__CANDIDATE_RELEASE_ID__` placeholders in the
   quickstart JSONL event files and write them to the temp directory
6. `flightdeck runs ingest` for both event files
7. `flightdeck release diff` (7-day window)
8. `flightdeck release promote` baseline → `local`
9. `flightdeck release history`
10. `flightdeck release verify` (checksum check against the on-disk bundle)
11. `flightdeck doctor`

All subprocesses use `subprocess.run(..., check=True)`. Any non-zero exit prints stderr and causes
the verifier to exit non-zero. On success it prints `quickstart_smoke: OK`.

**Executable resolution:** prefers `flightdeck` on `PATH` (`shutil.which`); falls back to
`sys.executable -m flightdeck.cli.main` so it works inside a bare `uv run` context without a
console-scripts install.

**JSON Schemas:** when **`src/flightdeck/`** models or **`scripts/generate_schemas.py`** change wire contracts, regenerate and match CI:

```bash
uv run python scripts/generate_schemas.py
git diff --exit-code schemas/
```

**Lockfile:** when you change **`pyproject.toml`** dependencies or extras, run **`uv lock`** and commit **`uv.lock`** so CI stays **`--frozen`**-reproducible.

## Web UI (React + Vite)

The browser UI under **`flightdeck serve`** `/` is built from **`web/`** into **`src/flightdeck/server/static/`** (committed artifacts). After changing UI source, rebuild and commit the static output so CI passes:

```bash
cd web
npm ci
npm run build
cd ..
git diff --exit-code src/flightdeck/server/static/
```

If that **`git diff`** fails, **`git add`** / commit everything under **`src/flightdeck/server/static/`** (hashed **`assets/*.js`**, **`index.html`**, etc.)—CI uses the same check after **`npm run build`**.

**Playwright:** from **`web/`**, **`npx playwright install chromium`** once, then **`npm run test:e2e`** (matches CI after the **`static/`** diff gate; see **`web/README.md`**).

**`npm run dev`:** proxies **`/v1`** to **`flightdeck serve`** on **`127.0.0.1:8765`** by default; copy **`web/.env.example`** to **`web/.env.local`** to set **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** when testing mutations against a token-protected server.

See **`web/README.md`** for PR-split guidance when iterating with agents.

Before pushing to an **org** remote, follow the maintainer checklist in **`CONTRIBUTING.md`** (`origin` = personal research, `org` = flightdeckdev).

## PyPI release (maintainers)

Merging to **`main` does not publish packages** — PyPI uploads are **tag-driven** (workflow **`.github/workflows/release-pypi.yml`**). The **PyPI project** is **`flightdeck-ai`** (`pip install flightdeck-ai`); the **`flightdeck`** CLI and **`import flightdeck`** layout are unchanged.

1. **PyPI:** add a **trusted publisher** for **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** — workflow **`release-pypi.yml`**. If PyPI offers **Environment name: (Any)**, you can still use a GitHub **Environment** named **`pypi`** for approval gates; otherwise match whatever you register on PyPI ([trusted publishers](https://docs.pypi.org/trusted-publishers/)).
2. **GitHub:** Settings → **Environments** → create **`pypi`** (optional: required reviewers / wait timer before OIDC publish).
3. Bump **`version`** in **`pyproject.toml`** and **`src/flightdeck/__init__.py`**, update **`CHANGELOG.md`**, merge to **`main`**.
4. **`git tag vX.Y.Z`** (must match **`pyproject.toml`** exactly, e.g. **`v1.0.6`**) then **`git push origin vX.Y.Z`**.

The workflow runs **ruff**, **pytest**, schema drift, **`uv build`**, publishes **sdist + wheel** to **PyPI** via **OIDC** (no long-lived API token in repo secrets), enables **publish attestations**, and creates a **GitHub Release** with generated notes and **`dist/*`** assets.

If **PyPI** rejects **attestations** for your project, set **`attestations: false`** on **`pypa/gh-action-pypi-publish`** in **`.github/workflows/release-pypi.yml`** until the registry side is sorted.

## Local Demo

```bash
flightdeck init
flightdeck pricing import examples/quickstart/pricing-baseline.yaml
flightdeck pricing import examples/quickstart/pricing-candidate.yaml
flightdeck policy set examples/quickstart/policy.yaml
BASELINE=$(flightdeck release register examples/quickstart/baseline-release)
CANDIDATE=$(flightdeck release register examples/quickstart/candidate-release)

sed "s/__BASELINE_RELEASE_ID__/${BASELINE}/g" examples/quickstart/baseline-events.jsonl > baseline-events.jsonl
sed "s/__CANDIDATE_RELEASE_ID__/${CANDIDATE}/g" examples/quickstart/candidate-events.jsonl > candidate-events.jsonl

flightdeck runs ingest baseline-events.jsonl
flightdeck runs ingest candidate-events.jsonl

flightdeck release diff "$BASELINE" "$CANDIDATE" --window 7d
flightdeck release promote "$BASELINE" --env local --window 7d --reason "initial baseline"
flightdeck release history --agent agent_support --env local
```

For a fully runnable demo that generates matching run events after release registration:

```bash
./scripts/smoke.sh
```

**`scripts/smoke.sh`** is a Bash script for Unix/macOS/Git Bash that mirrors the manual demo above. It creates a fresh temporary workspace, registers both quickstart releases, writes a pair of synthetic run events (one baseline, one candidate) with the assigned release IDs substituted inline, ingests them, runs `release diff`, promotes the baseline, and shows history. It does **not** run `release verify` or `doctor` — use `flightdeck-quickstart-verify` for the full end-to-end check including those steps.

### Smoke-test script comparison

| Script | Platform | What it covers |
|--------|----------|----------------|
| `flightdeck-quickstart-verify` (or `scripts/quickstart_smoke.py`) | All (Python) | Full workflow: init → pricing → policy → register → ingest → diff → promote → history → **verify → doctor**. Used in CI. |
| `scripts/smoke.sh` | Unix / Git Bash | Abbreviated demo: same workflow minus `verify` and `doctor`. Generates events inline so it needs no pre-substituted fixtures. |
| `examples/ci/ledger_gate.py` | All (Python) | Policy-gate CI gate only: init → pricing → register → ingest → diff (`--fail-on-policy`). No promote. Used in CI workflow. |

## Adding a SQLite migration

Migrations are forward-only numbered steps in `src/flightdeck/storage.py`. The current
highest version is tracked by `LATEST_SCHEMA_MIGRATION_VERSION`.

1. **Add the migration block** inside `Storage.migrate()`. Follow the existing pattern:

   ```python
   # v4: short description of what this migration does.
   apply(4, [
       "ALTER TABLE some_table ADD COLUMN new_col TEXT;",
   ])
   ```

   For migrations that need data-backfill or conditional DDL (like v3's `ALTER TABLE` +
   `PRAGMA table_info` check), write the logic inline before inserting into
   `schema_migrations`, similar to the `if 3 not in applied:` block.

2. **Bump `LATEST_SCHEMA_MIGRATION_VERSION`** at the top of `storage.py`:

   ```python
   LATEST_SCHEMA_MIGRATION_VERSION = 4   # was 3
   ```

3. **Add a `doctor` / `test_doctor.py` assertion** if the migration introduces a new
   invariant that `flightdeck doctor` should verify (e.g. a contiguous sequence or a
   foreign-key pointer). Update `test_doctor.py` to expect the new migration version.

4. **Update `docs/operations-and-policy.md § Schema migrations`** table to document the
   new version number and what it changes.

5. **Run the full test suite** to confirm the migration applies cleanly on a fresh DB
   and on a DB that already has the previous version applied:

   ```bash
   uv run python -m pytest tests/test_doctor.py tests/test_spine.py -v
   ```

### Migration constraints

- All migrations are **additive**; never drop columns or rename them without a new
  `api_version` major bump.
- Migrations are applied inside the same `conn.execute` autocommit context as the
  `CREATE TABLE IF NOT EXISTS` block; for large backfills consider using `transaction()`
  explicitly to avoid partial writes.
- `Storage.migrate()` is idempotent — calling it multiple times on the same DB is safe.
  `flightdeck doctor` calls it at startup as its first step.

---

## Local State

`flightdeck init` creates `flightdeck.yaml`. By default, local SQLite data lives at:

```text
.flightdeck/flightdeck.db
```

## Troubleshooting

If your OS temp directory is restricted, set `TMPDIR`, `TEMP`, or `TMP` to a repo-local `.tmp`
directory before running tests.

On some Windows setups, pytest may fail to create or clean its temp directories under the default
`%TEMP%` path. If you see `PermissionError` errors mentioning `pytest-of-...` or `pytest`, point temp
dirs at the repo-local `.tmp/` directory:

```powershell
$env:TEMP = (Resolve-Path .tmp).Path
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
uv run python -m pytest
```

By default, `tests/conftest.py` creates **`.tmp/`** at import (for **`--basetemp=.tmp/pytest`**) and redirects `TEMP`/`TMP` into that folder during pytest on Windows. Set
`FLIGHTDECK_USE_SYSTEM_TEMP=1` if you want to force pytest to use your normal OS temp directory instead.

If your shell does not activate virtual environments in the same way as the examples, use the
virtual environment's Python executable directly:

```bash
.venv/bin/python -m pytest
```

Use **`uv run python -m pytest`** from the repo root so imports like **`from tests.test_spine import …`** resolve the same way as in CI.

## Environment variables

| Variable | Component | Description |
|----------|-----------|-------------|
| `FLIGHTDECK_LOCAL_API_TOKEN` | Server | When set, `POST /v1/promote` and `POST /v1/rollback` require `Authorization: Bearer <token>`. Read endpoints and `POST /v1/events` are unaffected. See [docs/http-api.md](docs/http-api.md) and [SECURITY.md](SECURITY.md). |
| `FLIGHTDECK_USE_SYSTEM_TEMP` | Tests | Set to `1` to force pytest to use the OS default temp directory instead of the repo-local `.tmp/` directory. Useful on developer machines where `%TEMP%` works correctly (see *Troubleshooting* above). |
| `USER` / `USERNAME` | CLI | Used to populate the `actor` field on promote, rollback, and pricing import audit records. `USER` is checked first (Unix/macOS), then `USERNAME` (Windows); falls back to `"unknown"`. |
| `VITE_FLIGHTDECK_LOCAL_API_TOKEN` | Web dev server | Build-time variable for the React UI dev server (Vite). Copy `web/.env.example` → `web/.env.local` to set it when testing mutations through `npm run dev` against a token-protected server. |
| `VITE_DEV_PROXY_TARGET` | Web dev server | Overrides the Vite proxy target for `/v1` (default: `http://127.0.0.1:8765`). |
| `TMPDIR` / `TEMP` / `TMP` | Tests / OS | Standard temp directory environment variables. Set any of these to a repo-local `.tmp/` path if the OS default is restricted or permissions cause pytest failures. |
