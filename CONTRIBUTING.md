# Contributing

FlightDeck is **v1.0.0+** on a narrow local-first spine; changes should meet production infrastructure standards.

Contributions are accepted under the **Apache License, Version 2.0** (see **`LICENSE`**). The canonical tree is [github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck).

Human and AI contributors: follow **[AGENTS.md](AGENTS.md)** (full rules). For a short index, see **[CLAUDE.md](CLAUDE.md)**.

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

With **uv** (matches CI):

```bash
uv run python -m ruff check src tests
uv run python -m pytest
uv run flightdeck-quickstart-verify
```

With an activated **venv**:

```bash
python -m ruff check src tests
python -m pytest
flightdeck-quickstart-verify
```

If you change **`pyproject.toml`** dependencies, run **`uv lock`** and commit **`uv.lock`**. Use the same checks as **CI** (see **`AGENTS.md`**) before opening a PR.

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
