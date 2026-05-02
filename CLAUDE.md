# CLAUDE.md

Short entry for **Claude Code**, **Cursor**, and similar agents. **Authoritative policy:** root **`AGENTS.md`** (mission, non-goals, contracts, verification, doctrine).

Canonical repository (full history and maintainer workflows): **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** (`main`).

## Read first

| Topic | Location |
|--------|------|
| Agent / contributor rules | `AGENTS.md` |
| Runtime integrations / adoption hooks (optional `flightdeck.integrations`, extras, boundaries) | `AGENTS.md` (non-goals), [docs/sdk-integrations.md](docs/sdk-integrations.md), `src/flightdeck/integrations/`, [examples/integration/adoption/](examples/integration/adoption/) |
| Cursor IDE rules (CI artifacts, web static) | `.cursor/rules/flightdeck-ci-artifacts.mdc` |
| Setup and local demo | `DEVELOPMENT.md` |
| CLI flags and exit codes | [README.md](https://github.com/flightdeckdev/flightdeck/blob/main/README.md) (canonical repo) |
| v1 direction | [RELEASE_NOTES.md](https://github.com/flightdeckdev/flightdeck/blob/main/RELEASE_NOTES.md) |
| Shipped 0.x behavior snapshot | [RELEASE_NOTES.md](https://github.com/flightdeckdev/flightdeck/blob/main/RELEASE_NOTES.md) |
| Backlog and milestone status | [ROADMAP.md](https://github.com/flightdeckdev/flightdeck/blob/main/ROADMAP.md) |
| GA / release notes | `RELEASE_NOTES.md`, `CHANGELOG.md` |
| Org publish & staging (maintainer) | [CONTRIBUTING.md](https://github.com/flightdeckdev/flightdeck/blob/main/CONTRIBUTING.md) |
| Repo layout & CODEOWNERS | `.github/CODEOWNERS`, [CONTRIBUTING.md](https://github.com/flightdeckdev/flightdeck/blob/main/CONTRIBUTING.md) |

## Verify before you finish

With **uv** (recommended):

```bash
uv sync --frozen --extra dev
uv run python -m ruff check src tests
uv run python -m pytest
uv run flightdeck-quickstart-verify
uv run flightdeck --help
```

If you changed **Pydantic / wire models** affecting **`schemas/`**: **`uv run python scripts/generate_schemas.py`**, then **`git diff --exit-code schemas/`** must be clean—commit **`schemas/`** updates with the PR.

If you changed **`web/`** (React UI): from **`web/`**, run **`npm ci`** then **`npm run build`**, then from the repo root **`git diff --exit-code src/flightdeck/server/static/`** must be clean—commit all updates under that path (CI fails otherwise). When behavior changes, run **`npm run test:e2e`** from **`web/`**.

If you changed **`pyproject.toml`** integration extras or **`src/flightdeck/integrations/`** tests: run **`uv lock`**, commit **`uv.lock`**, and **`uv sync --frozen --extra dev --extra integrations-ci`** (see **`DEVELOPMENT.md`**) to match the CI integrations job.

Details: **`AGENTS.md`** (Verification), **`DEVELOPMENT.md`**, and **`.cursor/rules/flightdeck-ci-artifacts.mdc`**.

With **pip** + venv: use **`python -m …`** equivalents in **`DEVELOPMENT.md`**.

**Windows:** if `python` is not on `PATH`, use `py -3` for the same commands (or install **uv** and use **`uv run`**).

## Repo shape

Python package under `src/flightdeck/` (optional **`flightdeck.integrations`** under the same tree). Tests in `tests/`. Examples in `examples/quickstart/` and **`examples/integration/adoption/`**. JSON Schemas under `schemas/` (regenerate with **`uv run python scripts/generate_schemas.py`** when models change). Browser UI source in **`web/`**; production bundle committed under **`src/flightdeck/server/static/`** (rebuild with **`npm run build`** in **`web/`**). After **`pyproject.toml`** dependency edits, run **`uv lock`** and commit **`uv.lock`**.
