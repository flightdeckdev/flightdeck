# AGENTS.md

## Repository model (research vs canonical)

This tree is usually a **personal-account research repo** (`origin` → your GitHub user): local experimentation, WIP, and broad refactors are acceptable.

**Organization repos** — canonical product: **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** under [flightdeckdev](https://github.com/flightdeckdev). Only **relevant**, standards-meeting changes (tests, ruff, no secrets, changelog/version when releasing) should be pushed or PR’d there—typically via a second remote **`org`** (workflow notes live in **`CONTRIBUTING.md`** in this clone).

When implementing features, prefer **small, PR-shaped slices** that could ship to an org repo without extra cleanup. Do not conflate “saved in research” with “ready for org push.”

Extended maintainer docs (research workflow, org checklist, canonical publish) live on **`main`** in that repository. This clone stays compact and keeps practical contributor guidance in **`CONTRIBUTING.md`**. Claude Code / short entrypoint: **`CLAUDE.md`**. Cursor IDE: project rules under **`.cursor/rules/`** (for example **`flightdeck-ci-artifacts.mdc`** for web static + schema gates).

## Mission

FlightDeck helps teams **ship AI agents safely** with **release diffs**, **runtime evidence**, and **policy gates**.
The core product promise is trustworthy release safety: version releases, ingest runtime evidence, compare diffs, and gate
promotion with policy.

## Current Wedge

Economic and operational safety for AI releases.

## Non-goals

Do not add:

- prompt IDEs
- in-product **agent orchestration frameworks** (FlightDeck does not execute LangGraph/CrewAI-style graphs as core product behavior or become the default runtime for user workflows)
- dashboards before CLI workflow is proven
- gateways/proxies by default
- compliance scanners
- fine-tuning ops
- **broad plugin systems** (no dynamic plugin registry, no implicit third-party load-by-name in core)

**Allowed (adoption glue):** optional, explicitly declared **`[project.optional-dependencies]`** extras that install thin **`flightdeck.integrations.*`** helpers. Those modules only map third-party telemetry into **`RunEvent`** / HTTP ingest and strengthen **developer onboarding** and **runtime evidence**; they do not replace the CLI ledger or ship an embedded orchestrator.

## Public contracts

Treat these as **stable API** unless a change explicitly marks an experimental path:

- **CLI:** synopsis, flags, exit codes — `flightdeck --help` plus command help output (normative for scripting in this slim clone).
- **On-disk / wire:** `release.yaml`, run events, pricing imports, policy shape — **`schemas/`** (generated; drift caught in CI) plus compatibility notes in **`RELEASE_NOTES.md`**.
- **v1 / GA direction** (migrations, checksums, trust boundaries, defaults): **`RELEASE_NOTES.md`** and shipped CLI/schema behavior.
- **Backlog and milestone status:** **`ROADMAP.md`**.
- **Optional Python `flightdeck.integrations`:** SemVer-tracked but **experimental** until **`RELEASE_NOTES.md`** / **`CHANGELOG.md`** state otherwise. Not the same stability bar as CLI + **`RunEvent`** wire JSON unless explicitly promoted; prefer **`POST /v1/events`** and **`schemas/v1/run_event.schema.json`** as the normative integration surface.

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
- **Shipped web bundle** (**`web/`** → committed **`src/flightdeck/server/static/`**) and **schema drift** (**`schemas/`**, regenerate via Verification below) when your change touches UI or Pydantic wire shapes.
- **Trust boundaries** (diff, pricing, policy, promotion, serve host binding).
- **Cross-platform ergonomics** (Windows paths, line endings on fixtures, temp dirs).

## Verification

Recommended (**[uv](https://docs.astral.sh/uv/)** — see **`DEVELOPMENT.md`**):

```bash
uv sync --frozen --extra dev
uv run python -m ruff check src tests
uv run python -m pytest
uv run flightdeck-quickstart-verify
uv run flightdeck --help
```

After editing Pydantic models, regenerate schemas and ensure a clean diff:

```bash
uv run python scripts/generate_schemas.py
git diff --exit-code schemas/
```

After editing the **browser UI** under **`web/`** (for example **`web/src/`**), rebuild the committed static tree that **`flightdeck serve`** ships, then confirm CI’s static gate is clean (same check as **`.github/workflows/ci.yml`**):

```bash
cd web
npm ci
npm run build
cd ..
git diff --exit-code src/flightdeck/server/static/
```

Commit every change under **`src/flightdeck/server/static/`** (including new hashed **`assets/*.js`** and **`index.html`** script tags). **`npm run build`** already runs LF normalization via **`web/scripts/normalize-static-lf.mjs`**. For UI behavior, run **`npm run test:e2e`** from **`web/`** (Playwright runs in CI right after the static diff).

Fallback (activated **venv** or global tools): the same steps with **`python -m …`** / **`python scripts/…`** as in **`DEVELOPMENT.md`**.

On **Windows**, use `py -3` in place of `python` if that is how your environment is set up. If pytest temp dirs fail with permissions, see **`DEVELOPMENT.md`** / **`tests/conftest.py`**.

**CI bar** (mirrors **`.github/workflows/ci.yml`** on **CPython 3.14**): see the workflow for the exact sequence; includes **`uv sync --frozen --extra dev`**, **`web/`** **`npm ci`** + **`npm run build`** + **`git diff --exit-code`** on **`static/`**, Playwright **`npm run test:e2e`**, **ruff**, **pytest**, schema drift check, **`flightdeck-quickstart-verify`**, **`flightdeck --help`**. When you change **`pyproject.toml`** optional extras (including **`flightdeck.integrations`** extras), run **`uv lock`** and commit **`uv.lock`**. The workflow may include a separate **integrations** job that **`uv sync`**s **`dev`** plus selected integration extras and runs targeted tests.

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
