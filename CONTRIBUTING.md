# Contributing

FlightDeck is **v1.0.0+** on a narrow local-first spine; changes should meet production infrastructure standards.

Contributions are accepted under the **Apache License, Version 2.0** (see **`LICENSE`**). The canonical tree is [github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck).

Human and AI contributors: follow **[AGENTS.md](AGENTS.md)** (full rules). For a short index, see **[CLAUDE.md](CLAUDE.md)**.

## Local Setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

## Verify

```bash
python -m ruff check src tests
python -m pytest
python scripts/quickstart_smoke.py
```

Use the same commands as **CI** (see **`AGENTS.md`**) before opening a PR.

## Private files and pushing to GitHub

Do not commit credentials, customer data, internal strategy docs, or local ledger data. The repo ignores **`.flightdeck/`**, **`.env*`**, optional **`private/`** / **`secrets/`**, and common key/credential patterns—see **`.gitignore`** and **[SECURITY.md](SECURITY.md)**.

If this clone is your **research repo** (personal `origin`), treat **[docs/research-workflow.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/research-workflow.md)** and **[docs/git-remotes.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/git-remotes.md)** as the source of truth for what may go to org remotes vs what stays local.

Before the **first push** to an org remote (or any push that should represent “org standards”), follow **[docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)**. The **[flightdeckdev](https://github.com/flightdeckdev)** org is for planned repos when you are ready; prefer **one solid default repo** until a real split is needed.

## Pull Requests

Keep PRs small and focused. Include tests for behavior changes and docs for user-facing CLI,
schema, or workflow changes.

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
