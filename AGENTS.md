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

Run before finalizing changes:

```bash
python -m ruff check src tests
python -m pytest
python scripts/quickstart_smoke.py
```

On **Windows**, use `py -3` in place of `python` if that is how your environment is set up. If pytest temp dirs fail with permissions, see **`DEVELOPMENT.md`** / **`tests/conftest.py`**.

**CI bar** (same commands locally before a PR): **`ruff check`**, **`pytest`**, **`scripts/generate_schemas.py`** + no **`schemas/`** diff, **`scripts/quickstart_smoke.py`**, **`flightdeck --help`**.

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
