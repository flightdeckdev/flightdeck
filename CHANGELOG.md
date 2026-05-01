# Changelog

All notable changes to FlightDeck will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/). From **v1.0.0**, documented CLI behavior (**[docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md)** on the canonical **`main`** branch), committed **`schemas/v1/`**, and **`POST /v1/events`** payloads with **`api_version` `v1`** are treated as stable public contracts unless a release notes a semver-major bump.

## Unreleased

### Added

- **`uv.lock`** and **[uv](https://docs.astral.sh/uv/)**-based workflow: **`uv sync --extra dev`** / **`uv sync --frozen --extra dev`** for reproducible installs; **`uv run …`** for commands (see **`DEVELOPMENT.md`**).
- **CI:** **`astral-sh/setup-uv`** with **`uv sync --frozen --extra dev`** and **`uv run python -m …`** (avoids **`uv run pytest`** path quirks with **`from tests.…`** imports).
- **`.github/workflows/release-pypi.yml`:** on push of **`vMAJOR.MINOR.PATCH`**, verify tag matches **`pyproject.toml`** and **`src/flightdeck/__init__.py`**, run **ruff** / **pytest** / schema drift, **`uv build`**, publish to **PyPI** via **OIDC** trusted publishing (**publish attestations**), and create a **GitHub Release** with **`dist/*`** assets (**`softprops/action-gh-release`**).
- **`tests/test_version_consistency.py`:** assert **`pyproject.toml`** **`version`** matches **`flightdeck.__version__`** (same invariant as the release workflow).

### Fixed

- **`diff_releases` zero policy sample thresholds:** `Policy.min_candidate_runs`, `Policy.min_baseline_runs`, and `Policy.min_low_runs` set to **`0`** now correctly override workspace config defaults to `0` instead of being silently ignored. Previously, `or`-based fallback treated `0` as falsy and fell back to the config value (typically `500` / `50`). Fixed by using explicit `is not None` checks. A policy can now unconditionally accept any sample size by setting thresholds to `0` — for example, to allow diffs over empty event windows without a confidence downgrade.
- **`Storage.insert_promotion_record` transaction isolation:** the policy-fail path that writes a blocked promotion record now uses `transaction()` (SQLite `BEGIN IMMEDIATE`) instead of a bare `connect()` (autocommit). Previously, a blocked promotion could write its audit record without holding an exclusive write lock, allowing a racing writer to interleave and produce a non-contiguous `audit_seq`. The `commit_promotion` path (policy-pass) was already correct. Also consolidates `utc_now` from `models` as the single source of truth (removed duplicate in `storage.py`).

### Changed

- **`tests/conftest.py`:** create repo **`.tmp/`** at import time so **`pytest --basetemp=.tmp/pytest`** works on fresh checkouts and **Linux** CI (parent dir is no longer Windows-only).
- **`pyproject.toml` `[project] name`:** **`flightdeck-ai`** to match the **PyPI** trusted-publisher project; install with **`pip install flightdeck-ai`** / **`uv add flightdeck-ai`** (CLI remains **`flightdeck`**, imports **`flightdeck.*`**).
- **Contributor docs** (**`README.md`**, **`DEVELOPMENT.md`**, **`CONTRIBUTING.md`**, **`AGENTS.md`**, **`CLAUDE.md`**, **`.cursorrules`**): prefer **uv**; keep **pip** / **`python -m venv`** as fallback.
- **Python:** **`requires-python >=3.14,<3.15`**, **`.python-version`**, PyPI classifiers, **Ruff** `target-version`, **`uv.lock`**, and **CI** matrices now target **CPython 3.14** only (replacing broader **3.11–3.14** testing).

## 1.0.1 - 2026-05-01

### Added

- **`.gitattributes`:** force **LF** for **`tests/fixtures/golden_bundle/`** so checkout line endings do not change the pinned bundle digest (matches the **0.7.0** changelog intent).

### Changed

- **Slim distribution:** this repository omits the full in-tree **`docs/`** tree, org mirror scripts, and **`verify-repo-standards`** wrappers. Narrative docs and maintainer runbooks live on **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)**; in-repo links now point there where applicable.
- **`pyproject.toml`:** OpenTelemetry packages are **optional** only (**`telemetry`** / **`all`** extras); the default install matches the **1.0.0** dependency story (core does not import OpenTelemetry).
- **`.pre-commit-config.yaml`:** **ruff** replaces **black** / **isort**; **`ruff-pre-commit`** pinned to **v0.15.12** to match **`dev`** (**`ruff==0.15.12`**).
- **CI:** Python **3.13** and **3.14** added to the Ubuntu and Windows matrices (superseded by **3.14**-only policy; see **Unreleased**).
- **`pyproject.toml`:** default **`pytest --basetemp=.tmp/pytest`** so local runs avoid Windows **`PermissionError`** on **`%TEMP%\pytest-of-*`**.
- **`pre-commit-hooks`:** bumped to **v5.0.0**.

### Removed

- **`tests/test_sync_export_public.py`** (depended on export tooling not shipped in this tree).

## 1.0.0 - 2026-04-30

### Added

- **v1.0.0 GA freeze** narrative: **`RELEASE_NOTES.md`**, **`docs/spec-v1-forward.md`**, **`docs/v1-next-steps.md`** (archived internal planning under **`docs/reviews/`** remains **development-clone only**).

### Changed

- **v1.0.0 GA freeze:** stable contracts for the local-first spine summarized in **[RELEASE_NOTES.md](RELEASE_NOTES.md)** (trust boundaries, SQLite migrations, payload versioning).
- **`pyproject.toml`**: **Development Status :: 5 - Production/Stable** on PyPI classifiers.
- **Dependencies:** **`opentelemetry-api`**, **`opentelemetry-sdk`**, and **`opentelemetry-exporter-otlp`** removed from default installs; added optional **`telemetry`** extra (included in **`all`**) for forward OTLP work — core code did not import OpenTelemetry.

## 0.9.0 - 2026-04-30

### Added

- **[RELEASE_NOTES.md](RELEASE_NOTES.md)**: maintainer-facing trust boundaries, SQLite upgrades, pre-1.0 vs **v1.0.0** freeze intent, payload **`api_version`** behavior.
- **`tests/fixtures/json/`**: minimal golden JSON for **`RunEvent`**, **`ReleaseArtifact`**, **`PricingTable`**, **`Policy`**; **`tests/test_schemas.py`** validates each fixture against Pydantic models.
- **HTTP ingest tests:** **`POST /v1/events`** rejects empty **`api_version`**, wrong casing (**`V1`**), JSON **`null`**; accepts omitted **`api_version`** (defaults to **`v1`**); stable **`detail`** string for **`v2`** rejections.
- **[CLAUDE.md](CLAUDE.md)**: short agent entry (must-read table, verify commands, Windows note).
- **0.9 → 1.0** sequencing captured in **`docs/v1-next-steps.md`** (detailed milestone plans archived under **`docs/reviews/`** in maintainer clones only).

### Changed

- **[AGENTS.md](AGENTS.md)**: public contracts section, large-change review checklist, expanded verification (including **`quickstart_smoke.py`**), PR-shaped slice guidance, pointers to **`CLAUDE.md`** and forward spec.
- **[.cursorrules](.cursorrules)**: slimmed to defer to **`AGENTS.md`** / **`CLAUDE.md`** and the same verify bar.
- **[VERSIONING.md](VERSIONING.md)**: database migrations describe shipped numbered SQLite migrations (replacing stale “future work” wording); **Approaching 1.0.0** pointer to **`RELEASE_NOTES.md`** / **`docs/v1-next-steps.md`**.

## 0.8.0 - 2026-04-30

### Added

- **[docs/cli.md](docs/cli.md)**: CLI reference (synopsis, flags, exit codes, pointers to quickstart examples).
- **`scripts/quickstart_smoke.py`**: cross-platform quickstart smoke (**no bash**): temp workspace, Python placeholder substitution, **`release verify`**, **`doctor`**.
- **CI:** run quickstart smoke on **Ubuntu** and **Windows** matrix jobs (alongside pytest and schema drift).
- **Tests:** `tests/test_quickstart_smoke.py` exercises the smoke script.
- **0.8 milestone planning** (CLI + CI): archived under **`docs/reviews/`** in development clones; shipped artifacts are **`docs/cli.md`** and **`scripts/quickstart_smoke.py`** above.

### Changed

- **[docs/quickstart.md](docs/quickstart.md)**: recommend **`python scripts/quickstart_smoke.py`** on Windows; bash flow kept as optional.
- **[docs/architecture.md](docs/architecture.md)**: deferred section updated for shipped SDK / rollback / serve / doctor / verify.
- **`scripts/verify-repo-standards.sh`** / **`.ps1`**: run **`quickstart_smoke.py`** after pytest (same bar as CI).

## 0.7.0 - 2026-04-30

### Added

- **`flightdeck release verify <release_id> --path …`**: compares the checksum stored at registration with **`bundle_checksum`** on a supplied directory or `release.yaml` file; **exit code 2** on mismatch (**1** for normal CLI errors).
- **Committed golden bundle** `tests/fixtures/golden_bundle/` with a **pinned SHA-256** asserted in CI (Linux + Windows).
- **`.gitattributes`**: force **LF** for the golden fixture path so line-ending normalization on checkout does not change the digest.
- **0.7 milestone planning** (golden bundle / verify): archived under **`docs/reviews/`** in development clones; see **`tests/fixtures/golden_bundle/`** and **`flightdeck release verify`** above.

### Changed

- **`flightdeck.bundle`**: skip **symlink** files when hashing bundles (determinism + safety); POSIX test in **`tests/test_bundle_golden_fixture.py`** (skipped on Windows where symlink creation is often unavailable).
- **CI:** run **`python scripts/generate_schemas.py`** then **`git diff --exit-code schemas/`** on Ubuntu and Windows to catch hand-edited schema drift.

## 0.6.0 - 2026-04-30

### Added

- **Apache License, Version 2.0:** root **`LICENSE`** (from [apache.org](https://www.apache.org/licenses/LICENSE-2.0.txt)), **`NOTICE`**, and **`pyproject.toml`** `license = "Apache-2.0"` aligned with the canonical org repo [flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck).
- **SQLite migration 3:** `release_actions.audit_seq` (backfilled in `created_at` order), **`UNIQUE`** index **`idx_release_actions_audit_seq`**, and automatic assignment on insert via **`Storage._next_audit_seq`**.
- **`PromotionRecord.audit_seq`**: optional on write; populated when listing actions from storage.
- **`Storage.check_release_actions_audit_seq()`** and **`flightdeck doctor`** extension: verifies **contiguous** non-null **`audit_seq`** values `1..max` (gap / tamper hint per forward spec).

### Changed

- **README** / **[docs/github-organization.md](docs/github-organization.md)** / **[docs/git-remotes.md](docs/git-remotes.md):** point at **`https://github.com/flightdeckdev/flightdeck`**.

## 0.5.1 - 2026-04-30

### Added

- **`flightdeck doctor`**: read-only checks for **SQLite schema migrations** (through `LATEST_SCHEMA_MIGRATION_VERSION`) and **promoted release pointers** (each `promoted_releases.release_id` exists in `releases`).
- **`flightdeck.storage`**: `list_applied_migrations()`, `list_promoted_pointers()`, and **`LATEST_SCHEMA_MIGRATION_VERSION`** (keep in sync when adding migrations).

## 0.5.0 - 2026-04-30

### Added

- **[docs/v1-next-steps.md](docs/v1-next-steps.md)**: Maintainer v1 gap analysis (P0/P1/P2), milestone sequencing (0.5–1.0), and risk callouts; tracks implementation status as work lands.
- **`flightdeck serve`**: warns when `--host` is not loopback (trust boundary; see forward spec §4).
- **`POST /v1/events`**: rejects unsupported `api_version` before Pydantic with a clear 400 detail.
- **Ledger tests** (`tests/test_ledger.py`): `diff_releases` rejects cross-agent and mixed-agent run batches.

### Changed

- **Implicit default policy** (no `flightdeck policy set`): `require_high_diff_confidence` now defaults to **`true`**, matching the `Policy` model and **v1 GA** direction. Quickstart and tests keep explicit **`require_high_diff_confidence: false`** where low-sample demos need it.
- **`diff_releases`**: enforces a single shared `agent_id` across baseline and candidate run events when both sides are non-empty (defense in depth vs CLI-only checks).
- **`Storage.insert_release`**: uses **`transaction()`** for the same atomic discipline as promotion paths.
- **CLI** `release diff`, `release promote`, and `release rollback`: surface `ValueError` from `diff_releases` as `ClickException`.

## 0.4.2 - 2026-04-30

### Added

- **[docs/git-remotes.md](docs/git-remotes.md)**: configure **`origin`** (personal research) vs **`org`** ([flightdeckdev](https://github.com/flightdeckdev) canonical), with everyday `git push` examples.

### Changed

- **Research workflow docs** ([docs/research-workflow.md](docs/research-workflow.md), [RESEARCH.md](RESEARCH.md), [AGENTS.md](AGENTS.md), [.cursorrules](.cursorrules), [docs/github-organization.md](docs/github-organization.md)) now state explicitly: **personal account** = research clone; **org** = user-facing canonical.

## 0.4.1 - 2026-04-30

### Added

- **[docs/github-organization.md](docs/github-organization.md)** for the **[flightdeckdev](https://github.com/flightdeckdev)** org: when to add repos, pre-push checklist, private-file policy.
- **`scripts/verify-repo-standards.sh`** / **`.ps1`**: run ruff + pytest before pushing.

### Changed

- **`.gitignore`**: ignore **`.flightdeck/`** (local DB/config), **`private/`**, **`secrets/`**, common cert/credential patterns, **`Thumbs.db`**.
- **Release bundle checksum** moved to **`flightdeck.bundle`**: LF normalization for text-like extensions so CRLF vs LF does not change the digest; `.git` / `__pycache__` under a bundle are excluded from hashing.
- **SQLite migration 2**: index on `run_events(release_id, timestamp)` for ledger queries.

### Security / hygiene

- **[SECURITY.md](SECURITY.md)** and **[CONTRIBUTING.md](CONTRIBUTING.md)** expanded with secret/local-path guidance and link to the org push gate doc.

## 0.4.0 - 2026-04-30

### Added

- **Forward v1 specification** (`docs/spec-v1-forward.md`): normative direction for v1 GA (versioning, migrations, bundle checksum canonicalization, trust boundaries, diff/policy defaults, SDK testing discipline). `docs/spec.md` remains the frozen 0.x implementation narrative; new guarantees land here first.
- **SDK unit test** using `httpx.MockTransport` so the Python client is covered without relying on sync ASGI transport quirks.

### Changed

- README status and documentation index now point at the forward v1 spec and reflect shipped local HTTP + minimal SDK.

## 0.3.0 - 2026-04-30

### Added

- Local HTTP ingestion service: `flightdeck serve` with `POST /v1/events`.
- Minimal HTTP client helper: `flightdeck.sdk.client.FlightdeckClient`.
- `flightdeck release rollback` with the same policy gate + audit trail as `promote`.
- Append-only pricing import audit log (`pricing_import_audit`) and required `--reason` for `pricing import --replace`.
- Public JSON Schemas under `schemas/v1/` plus `scripts/generate_schemas.py`.
- Policy can require HIGH diff confidence (`require_high_diff_confidence`, default `true` on explicit policies).

### Fixed

- Atomic promotion: audit record + promoted pointer update now share a single DB transaction.
- SQLite connections enable WAL + busy timeout to reduce Windows locking issues.
- Safer `--window` parsing errors are surfaced as `ClickException` (no tracebacks).

## 0.2.0 - 2026-04-30

### Added

- Local release registry (`flightdeck release register`, `flightdeck release list`, `flightdeck release show`).
- Run event ingestion (`flightdeck runs ingest`).
- Trusted `flightdeck release diff` with confidence labels, explicit `--window`, and ASCII `delta` output.
- Per-release pricing for diffs (baseline and candidate are costed against their own `pricing_reference`).
- Cross-agent diff rejection by default.
- Immutable pricing table import with explicit `--replace` and `flightdeck pricing show`.
- Active policy object (`flightdeck policy set`, `flightdeck policy show`) used for diff evaluation and promotion.
- Policy-gated `flightdeck release promote` with required `--reason` and `flightdeck release history`.

### Notes

- Cost estimates are **model token costs** only; tool spend pricing is not implemented yet.

### Fixed

- Windows: avoid pytest temp-dir permission issues by redirecting `TEMP`/`TMP` into a repo-local `.tmp/`
  directory during pytest (see `tests/conftest.py`), with an opt-out via `FLIGHTDECK_USE_SYSTEM_TEMP=1`.
