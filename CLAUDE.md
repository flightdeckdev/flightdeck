# CLAUDE.md

Short entry for **Claude Code**, **Cursor**, and similar agents. **Authoritative policy:** root **`AGENTS.md`** (mission, non-goals, contracts, verification, doctrine).

Canonical repository (full **`docs/`** tree and org workflows): **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** (`main`).

## Read first

| Topic | Location |
|--------|------|
| Agent / contributor rules | `AGENTS.md` |
| Setup and local demo | `DEVELOPMENT.md` |
| CLI flags and exit codes | [docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md) (canonical repo) |
| v1 direction | [docs/spec-v1-forward.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md) |
| Shipped 0.x behavior snapshot | [docs/spec.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec.md) |
| Backlog and milestone status | [docs/v1-next-steps.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/v1-next-steps.md) |
| GA / release notes | `RELEASE_NOTES.md`, `CHANGELOG.md` |
| Org publish & staging (maintainer) | [docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md) |
| Repo layout & CODEOWNERS | `.github/CODEOWNERS`, [docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md) |

## Verify before you finish

```bash
python -m ruff check src tests
python -m pytest
python scripts/quickstart_smoke.py
```

**Windows:** if `python` is not on `PATH`, use `py -3` for the same commands.

## Repo shape

Python package under `src/flightdeck/`. Tests in `tests/`. Examples in `examples/quickstart/`. JSON Schemas under `schemas/` (regenerate with `python scripts/generate_schemas.py` when models change).
