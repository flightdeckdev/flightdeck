## Summary

## Why

## Changes

## Validation

Run the same checks as **CI** (see **`.github/workflows/ci.yml`**) before opening / updating the PR:

- [ ] `uv sync --frozen --extra dev`
- [ ] `uv run python -m ruff check src tests`
- [ ] `uv run python -m pytest`
- [ ] `uv run python scripts/generate_schemas.py` then `git diff --exit-code schemas/` (if models/schemas touched)
- [ ] `cd web && npm ci && npm run build && cd .. && git diff --exit-code src/flightdeck/server/static/` (if **`web/src/`** or deps changed)
- [ ] `cd web && npx playwright install chromium && npm run test:e2e` (if **`web/`** changed)
- [ ] `uv run flightdeck-quickstart-verify`
- [ ] `uv run flightdeck --help`

With **pip** / venv only, use **`python -m …`** equivalents from **`DEVELOPMENT.md`**.

## Schema / Storage Impact

- [ ] None
- [ ] Schema change
- [ ] Storage change

## Risk

## Review

- [ ] **Requested review** from maintainers (**[CODEOWNERS](.github/CODEOWNERS)** → **`@flightdeckdev/maintainers`** on the org repo). On a **fork**, GitHub may not auto-request; use **Reviewers** on the PR.
- [ ] PR is **small and scoped** (see **`AGENTS.md`**); linked issue or release note intent noted if helpful.

## Notes
