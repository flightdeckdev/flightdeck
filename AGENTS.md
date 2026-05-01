# AGENTS.md

## Repository model (research vs canonical)

This tree is usually a **personal-account research repo** (`origin` → your GitHub user): local experimentation, WIP, and broad refactors are acceptable.

**Organization repos** — canonical product: **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** under [flightdeckdev](https://github.com/flightdeckdev). Only **relevant**, standards-meeting changes (tests, ruff, no secrets, changelog/version when releasing) should be pushed or PR’d there—typically via a second remote **`org`** (workflow: [git remotes](https://github.com/flightdeckdev/flightdeck/blob/main/docs/git-remotes.md)).

When implementing features, prefer **small, PR-shaped slices** that could ship to an org repo without extra cleanup. Do not conflate “saved in research” with “ready for org push.”

Extended maintainer docs (research workflow, org checklist, canonical publish) live on **`main`** in that repository (for example [research workflow](https://github.com/flightdeckdev/flightdeck/blob/main/docs/research-workflow.md), [GitHub organization](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)). This clone may omit those paths to stay small. Claude Code / short entrypoint: **`CLAUDE.md`**.

## Mission

FlightDeck is AI Release Governance for production agents. The core product promise is
trustworthy release safety: version releases, ingest runtime evidence, compare diffs, and gate
promotion with policy.

## Current Wedge

Economic and operational safety for AI releases.

## Non-goals

Do not add:

- prompt IDEs
- agent frameworks
- dashboards before CLI workflow is proven
- gateways/proxies by default
- compliance scanners
- fine-tuning ops
- broad plugin systems

## Public contracts

Treat these as **stable API** unless a change explicitly marks an experimental path:

- **CLI:** synopsis, flags, exit codes — canonical reference: **[docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md)** (normative for scripting).
- **On-disk / wire:** `release.yaml`, run events, pricing imports, policy shape — **`schemas/`** (generated; drift caught in CI), **[docs/spec.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec.md)** (0.x snapshot of what the code does today).
- **v1 / GA direction** (migrations, checksums, trust boundaries, defaults): **[docs/spec-v1-forward.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md)**. Prefer updating the forward spec for new v1 contracts; avoid expanding **`docs/spec.md`** as the rolling GA target.
- **Backlog and review status:** **[docs/v1-next-steps.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/v1-next-steps.md)**.

## Engineering rules

- Keep changes small and behavior-focused.
- Preserve the local-first CLI workflow.
- Treat schemas and CLI behavior as public contracts.
- Add tests for every behavior change.
- Prefer boring, explicit code over clever abstractions.
- Do not introduce empty enterprise scaffolding.
- Do not move modules into packages/apps until there is a real release boundary.

## Before large or multi-file changes

Do a short review pass for:

- **Contract drift** (CLI, JSON/YAML, SQLite columns consumers rely on).
- **Trust boundaries** (diff, pricing, policy, promotion, serve host binding).
- **Cross-platform ergonomics** (Windows paths, line endings on fixtures, temp dirs).

## Verification

Recommended (**[uv](https://docs.astral.sh/uv/)** — see **`DEVELOPMENT.md`**):

```bash
uv sync --frozen --extra dev
uv run python -m ruff check src tests
uv run python -m pytest
uv run python scripts/quickstart_smoke.py
```

After editing Pydantic models, regenerate schemas and ensure a clean diff:

```bash
uv run python scripts/generate_schemas.py
git diff --exit-code schemas/
```

Fallback (activated **venv** or global tools): the same steps with **`python -m …`** / **`python scripts/…`** as in **`DEVELOPMENT.md`**.

On **Windows**, use `py -3` in place of `python` if that is how your environment is set up. If pytest temp dirs fail with permissions, see **`DEVELOPMENT.md`** / **`tests/conftest.py`**.

**CI bar** (mirrors **`.github/workflows/ci.yml`** on **CPython 3.14**): **`uv sync --frozen --extra dev`**, **`uv run python -m ruff check src tests`**, **`uv run python -m pytest`**, **`uv run python scripts/generate_schemas.py`** + no **`schemas/`** diff, **`uv run python scripts/quickstart_smoke.py`**, **`uv run flightdeck --help`**.

Use a repo-local temp directory if the OS temp directory is restricted.

## Product doctrine

A feature must strengthen at least one:

- release artifact integrity
- runtime evidence
- safety ledger accuracy
- policy-gated promotion
- audit history
- developer onboarding

If it does not, it waits.

## Docs rules

Public docs explain implemented behavior and near-term roadmap. Internal product strategy, legal
notes, and fundraising/customer discovery material do not belong in this repo.

## Cursor Cloud specific instructions

**Single-service Python CLI** — no Docker, no external databases, no multi-service orchestration. SQLite is embedded (stdlib).

### Quick reference

| Action | Command |
|--------|---------|
| Install deps | `uv sync --extra dev` |
| Lint | `uv run python -m ruff check src tests` |
| Test | `uv run python -m pytest` |
| Smoke test | `uv run python scripts/quickstart_smoke.py` |
| Schema check | `uv run python scripts/generate_schemas.py && git diff --exit-code schemas/` |
| CLI help | `uv run flightdeck --help` |
| HTTP server | `uv run flightdeck serve --port 8765` (from a workspace with `flightdeck.yaml`) |

### Gotchas

- **Python 3.14 strict**: `requires-python = ">=3.14,<3.15"`. The update script installs it via `uv python install 3.14`.
- **`flightdeck doctor`** and most CLI commands require a `flightdeck.yaml` in cwd. Run `flightdeck init` first (creates the config + `.flightdeck/` SQLite dir).
- **`--frozen` flag**: CI uses `uv sync --frozen --extra dev`. For local dev, `uv sync --extra dev` (without `--frozen`) is fine unless you need lockfile-exact reproducibility.
- **Temp directory**: pytest is configured with `--basetemp=.tmp/pytest` (in `pyproject.toml`). The `.tmp/` directory is gitignored and auto-created by `tests/conftest.py`.
- **Schema drift**: after editing Pydantic models in `src/flightdeck/models.py`, run `uv run python scripts/generate_schemas.py` and commit any `schemas/` changes. CI will fail on drift.
