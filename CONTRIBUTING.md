# Contributing

FlightDeck is **v1.0.0+** on a narrow local-first spine; changes should meet production infrastructure standards.

Contributions are accepted under the **Apache License, Version 2.0** (see **`LICENSE`**). The canonical tree is [github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck).

Human and AI contributors: follow **[AGENTS.md](AGENTS.md)** (full rules). For a short index, see **[CLAUDE.md](CLAUDE.md)**. In **Cursor**, the project rule **[`.cursor/rules/flightdeck-ci-artifacts.mdc`](.cursor/rules/flightdeck-ci-artifacts.mdc)** (`alwaysApply`) summarizes the **web `static/`** and **`schemas/`** drift gates CI enforces.

## Who we are building for

The product ICP is **platform or ML engineering teams** (often about **5–30** people) at **Series B+**-style companies shipping **at least two** **LLM-backed agents** to production—teams that have already been burned by a **cost spike** or **quality regression** tied to a **prompt** or **model** change. Contributions should shorten their path to **versioned releases**, **ingested evidence**, **economic diffs**, and **policy-gated promote**—not broaden scope into orchestration or hosted tracing (see **[AGENTS.md](AGENTS.md)** non-goals).

## Local Setup

Recommended (**[uv](https://docs.astral.sh/uv/)** — see **`DEVELOPMENT.md`**):

```bash
uv sync --extra dev
```

Fallback (**pip**):

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

## Verify

With **uv** (core Python checks; see **`.github/workflows/ci.yml`** for the full job):

```bash
uv sync --frozen --extra dev
uv run python -m ruff check src tests
uv run python -m pytest
uv run flightdeck-quickstart-verify
uv run flightdeck --help
```

With an activated **venv**:

```bash
python -m ruff check src tests
python -m pytest
flightdeck-quickstart-verify
flightdeck --help
```

If you change **`pyproject.toml`** dependencies, run **`uv lock`** and commit **`uv.lock`**.

**Also run before a PR** (when relevant—same gates as CI):

- **Schemas:** `uv run python scripts/generate_schemas.py` then `git diff --exit-code schemas/`
- **Web UI:** `cd web && npm ci && npm run build && cd .. && git diff --exit-code src/flightdeck/server/static/`; if UI behavior changed, `cd web && npx playwright install chromium && npm run test:e2e`

Details, Windows notes, and doctrine: **`AGENTS.md`** (Verification), **`DEVELOPMENT.md`**, **`web/README.md`**.

## GitHub Pages (maintainers)

The **Deploy documentation to GitHub Pages** workflow publishes **`docs/`** on pushes to **`main`**. In the GitHub repo, use **Settings → Pages → Build and deployment → Source: GitHub Actions** so the workflow can attach the **`github-pages`** environment. The live URL is linked from the root **`README.md`** and **`pyproject.toml`** **`Documentation`** URL.

## Private files and pushing to GitHub

Do not commit credentials, customer data, internal strategy docs, or local ledger data. The repo ignores **`.flightdeck/`**, **`.env*`**, optional **`private/`** / **`secrets/`**, and common key/credential patterns—see **`.gitignore`** and **[SECURITY.md](SECURITY.md)**.

If this clone is your **research repo** (personal `origin`), use this file as the source of truth for what may go to org remotes vs what stays local.

Before the **first push** to an org remote (or any push that should represent “org standards”), follow the pre-push checklist in this file. The **[flightdeckdev](https://github.com/flightdeckdev)** org is for planned repos when you are ready; prefer **one solid default repo** until a real split is needed.

## Pull Requests

Keep PRs small and focused. Include tests for behavior changes and docs for user-facing CLI,
schema, or workflow changes.

Use the **[pull request template](.github/PULL_REQUEST_TEMPLATE.md)** checklist (same bar as **`.github/workflows/ci.yml`**). **Request review** from **[CODEOWNERS](.github/CODEOWNERS)** (`@flightdeckdev/maintainers` on the org repo); on a fork, add reviewers manually so the change gets eyes before merge.

## Commit Style

Use Conventional Commits:

- `feat(release): add immutable release registry`
- `fix(diff): cost baseline with baseline pricing table`
- `docs(repo): add ADR process`
- `test(policy): cover failed promotion history`

Useful scopes: `release`, `diff`, `ledger`, `pricing`, `policy`, `storage`, `cli`, `sdk`,
`server`, `schemas`, `docs`, `ci`, `repo`, `security`.

## Design Changes

Use an ADR for changes that affect schemas, storage, release semantics, public CLI behavior, or
the local-first architecture.

## AI-Assisted Contributions

AI-assisted code is allowed only when the contributor understands it, tests it, and accepts
responsibility for it.
