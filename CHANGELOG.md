# Changelog

All notable changes to FlightDeck will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/). From **v1.0.0**, documented CLI behavior (**[README.md](https://github.com/flightdeckdev/flightdeck/blob/main/README.md)** on the canonical **`main`** branch), committed **`schemas/v1/`**, and **`POST /v1/events`** payloads with **`api_version` `v1`** are treated as stable public contracts unless a release notes a semver-major bump.

## Unreleased

### Breaking

- **`POST /v1/events`:** uses the same **`FLIGHTDECK_LOCAL_API_TOKEN`** / loopback policy as promotion and rollback. Remote unauthenticated ingest is no longer accepted; set the env var and send **`Authorization: Bearer`** (Python SDK **`api_token=`**, or **`--api-token`** / env in **[examples/integration/emit_sample_events.node.mjs](examples/integration/emit_sample_events.node.mjs)**).
- **Python:** **`requires-python`** is **`>=3.11,<4`** (replaces **`>=3.14,<3.15`**). **`[tool.ruff] target-version`** is **`py311`**. CI follows **`.python-version`** (currently **3.12**).

### Changed

- **Docs / examples:** **`DEVELOPMENT.md`**, **`AGENTS.md`**, **`docs/sdk.md`**, **`docs/troubleshooting.md`**, **`examples/integration/README.md`**, **`examples/integration/adoption/README.md`**, **`examples/deploy/README.md`** — align with the Python range and ledger-write ingest model.

### Added

- **Experimental `flightdeck.integrations`:** optional extras **`integrations-langchain`**, **`integrations-temporal`**, **`integrations-openai-agents`**, and meta **`integrations-ci`** (CI job); thin mappers from OpenAI chat completions, Anthropic messages, OpenAI Agents–style results, LangChain callbacks, CrewAI-style manual totals, and Temporal-oriented **`labels`**. Docs: **`docs/sdk-integrations.md`**; examples: **`examples/integration/adoption/`**. Contributor policy updates in **`AGENTS.md`** / **`CLAUDE.md`**.

### Changed

- **Web Runs:** forensics — empty / offset / truncation messaging, export copy, trace band rows or **Group by trace_id**, **View** drawer (structured fields + full JSON, **session_id** / **span_id**, focus trap + return focus, **`aria-haspopup="dialog"`**), trace/status columns; **run-query** failures show a typed error card with **Retry**.
- **Web Diff:** scannable sections (policy, evidence window, pricing/catalog/hints, rollups), pre-query hint, `evaluated_at` when present; warn when imported **pricing table versions** or **providers** differ baseline vs candidate.
- **Web Actions:** workspace loading skeleton; numbered approval steps; pending **Refresh list** / **Use for confirm**; clearer confirms; approval-reason placeholder; **Rollback** danger-styled; **Actions** shows whether **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** is set (no value) and an inline hint when the server uses **Bearer** and the UI token is missing.
- **Web shell / Overview / CSS:** **Langfuse-style** left sidebar + main column (stacks on narrow viewports); skeleton loading on first load; **Overview** auto-polls timeline + metrics every **30s** when the tab is visible (silent refresh; no manual **Refresh** button); updates after **Actions** mutations via context; ledger metrics hints + links to **Diff** / **Runs**; Diff query **`aria-busy`**; **Security strip** `/health` loading + **Bearer** + client-token reassurance line; shared **focus-visible** / type scale / narrow breakpoints; **skip to main** (HashRouter-safe); **[ROADMAP.md](ROADMAP.md)** adds **Visual system** backlog item and theme deferral.
- **Examples / deploy / SECURITY / web README:** [examples/README.md](examples/README.md) end-to-end loop + **UI polish / operator flow** blurb; deploy checklist + **`restart: unless-stopped`**; **[SECURITY.md](SECURITY.md)** deploy pointer; **[web/README.md](web/README.md)** Playwright approval vs default runs.
- **Playwright:** `e2e-server.mjs` gates approval workspace on **`PW_FORCE_APPROVAL_WORKSPACE`** (set from config); **`reuseExistingServer: false`**; config sets approval workspace only when the CLI lists **exactly one** `e2e/*.spec.ts` path and it is **`actions-approval.spec.ts`** (avoids multi-spec argv; **`PW_WEBSERVER_APPROVAL`** no longer toggles the server so a stale value cannot break **`npm run test:e2e`**); **`actions-approval.spec.ts`** skips when **`GET /v1/workspace`** shows approval off (e.g. full suite with **`FD_E2E_FORCE_APPROVAL=1`**).

### Added

- **PostgreSQL ledger:** optional **`database_url`** in **`flightdeck.yaml`** (`postgresql://` or `postgres://`); install **`psycopg`** with **`uv sync --extra postgres`** (or **`pip install 'flightdeck-ai[postgres]'`**). Same schema migrations and API behavior as SQLite; run filters use **`::json`** predicates on **`event_json`**. **`flightdeck doctor --backup`** stays SQLite-only (use **`pg_dump`** for Postgres). Optional integration tests: **`FLIGHTDECK_TEST_POSTGRES_URL`** with the **`postgres`** extra.
- **`GET /v1/runs/export`** — NDJSON stream of the same filtered slice as **`GET /v1/runs`** (optional response headers when truncated).
- **`session_id`** / **`span_id`** query filters on **`GET /v1/runs`**, matching CLI/SDK, and **`offset`** pagination on run listings (with **`runs list`** / **`runs export`**).
- **Web Runs** page — query **`GET /v1/runs`** from the bundled UI.

## 1.1.2 - 2026-05-03

### Added

- **`trace_id` filter** on `GET /v1/runs`, `flightdeck runs list --trace-id`, and SDK `list_runs(trace_id=…)` — exact match on ingested `RunEvent.request.trace_id`.
- **`flightdeck runs export`** — write the same filtered run-event slice as **`runs list`** as **JSONL** (optional **`-o`** file; default stdout); **`--limit`** defaults to **500** (max **500**); prints a **stderr** warning when results are truncated.

### Changed

- **Examples / CI snippets:** **`flightdeck-ai>=1.1.2`** where version pins apply.

## 1.1.1 - 2026-05-02

### Added

- **`GET /v1/workspace`:** read-only JSON for operators and the web UI — **`promotion_requires_approval`**, **`pricing_catalog_configured`**, **`server_version`** (normative schema + Python SDK helper).
- **Web Actions:** Promote flow uses workspace flags — direct **`POST /v1/promote`** when approval is off; **request → list pending → confirm** when **`promotion_requires_approval`** is on, with clearer errors.
- **Docs:** README / **release-artifact** / **examples** / **web-ui** / **http-api** / **sdk** updates for the **v1.1.x** remainder; optional **`docs/pricing-catalog.md`**; **`examples/ci/promote_with_approval.sh`** and CI README **GitHub Actions** pattern for approval-gated promote.

### Changed

- **Examples / CI snippets:** **`flightdeck-ai>=1.1.1`** where version pins apply.
- **Positioning:** README, PyPI short description, CLI `--help`, and web header tagline emphasize outcome-oriented messaging (diffs, evidence, policy gates) plus README sections for stack fit and product comparisons.

## 1.1.0 - 2026-05-03

### Added

- **Pricing catalog:** optional `pricing_catalog_path` in `flightdeck.yaml` loads a `PricingCatalog` YAML; `POST /v1/diff` / `release diff` include additive `pricing.catalog` and `pricing.hints` (see `schemas/v1/pricing_catalog.schema.json`, `examples/pricing/catalog.sample.yaml`).
- **Promotion approval:** `promotion_requires_approval` in `flightdeck.yaml`; `POST /v1/promote/request`, `POST /v1/promote/confirm`, `GET /v1/promotion-requests`, and CLI `release promote-request` / `promote-confirm`.
- **Forensics:** `GET /v1/runs` and `flightdeck runs list` for read-only run event slices.
- **Deploy:** optional Helm chart under `examples/deploy/chart/flightdeck/`.
- **Examples:** `examples/fleet/README.md` and workspace template.
- **SQLite migration v4:** `promotion_requests` table.

### Changed

- **Examples / CI snippets:** **`flightdeck-ai>=1.1.0`** in Docker and PyPI gate samples.

## 1.0.6 - 2026-05-02

### Added

- **CLI `flightdeck doctor --backup PATH`:** SQLite online backup of the workspace database to **`PATH`** (parent directories created; file overwritten if present), then the usual doctor checks.
- **Examples:** **[examples/integration/emit_sample_events.node.mjs](examples/integration/emit_sample_events.node.mjs)** — **`POST /v1/events`** sample using built-in **`fetch`** (Node 18+); **[examples/integration/README.md](examples/integration/README.md)** adds **`curl`** + **`jq`** example.
- **Docs:** **[examples/deploy/README.md](examples/deploy/README.md)** — Compose **`/health`** healthcheck and **`doctor --backup`** / cron scheduling notes.
- **Roadmap:** **Phase 0** declared **closed**; **catalog-level** multi-provider pricing normalization called out under **mid-term productization** build items.
- **Tests:** **`test_doctor_backup_writes_valid_sqlite`** in **`tests/test_cli.py`**.

### Changed

- **Examples / CI snippets:** **`flightdeck-ai>=1.0.6`** in Docker and PyPI gate samples.

## 1.0.5 - 2026-05-02

### Added

- **CLI `release diff --output json`:** prints the same JSON object as **`POST /v1/diff`** (sorted keys) for **`jq`** / CI parsers; works with **`--fail-on-policy`** (JSON to stdout, then exit **1** on policy failure).
- **`POST /v1/diff`:** **`pricing.warnings`** — string list when baseline or candidate **`spec.runtime.model`** has no row in that side's imported pricing table (diagnostic only; **`policy`** unchanged). CLI prints matching **`WARNING:`** lines in text mode.
- **Web UI:** **Run diff** shows pricing warnings above the pricing/model-change banner; **Overview** adds a **Ledger metrics** card (**`GET /v1/metrics`**).
- **Docs:** **[docs/cli.md](docs/cli.md)** and **[docs/http-api.md](docs/http-api.md)** document **`--output json`** and **`pricing.warnings`**.
- **Tests:** **`test_release_diff_output_json_shape`**, **`test_release_diff_pricing_warnings_when_model_not_in_table`** in **`tests/test_spine.py`**; **`test_release_diff_fail_on_policy_with_json_output`** in **`tests/test_cli_contract.py`**; **`test_http_v1_diff_pricing_warnings_when_model_missing`** and **`pricing.warnings`** assertion on the happy path in **`tests/test_server_actions.py`**.

## 1.0.4 - 2026-05-03

### Added

- **HTTP `GET /v1/metrics`:** read-only JSON counters for the local ledger (`releases_total`, `pricing_tables_total`, `run_events_total`, `promoted_pointers_total`, `actions_total`, `actions_by_action`) plus `schema_version` and `generated_at`; backed by **`Storage.get_ledger_counters()`**.
- **`POST /v1/diff`:** `pricing.prices` — per-side input/output/cached-input USD per 1k tokens for the resolved model (mirrors table entries; helps separate tariff changes from token volume).
- **CLI `release diff`:** when pricing or model differs, prints **Per-1k token prices** after the existing NOTE line.
- **Web UI (Run diff):** shows per-1k input/output price deltas under the pricing/model-change banner when those numbers are present.
- **Docs:** [examples/README.md](examples/README.md) operating walkthrough; [docs/http-api.md](docs/http-api.md) documents **`GET /v1/metrics`** and **`pricing.prices`**; [docs/cli.md](docs/cli.md) documents the new diff output line.
- **Tests:** **`test_v1_metrics_returns_counters`** in **`tests/test_server_health.py`**; **`POST /v1/diff`** `pricing.prices` assertions on cross-model diff in **`tests/test_spine.py`**.

### Changed

- **Roadmap:** **Next release** and **Phase 0 progress** updated for **v1.0.4** (pricing diagnostic, examples index, metrics endpoint).
- **Examples / CI snippets:** **`flightdeck-ai>=1.0.4`** in Docker and PyPI gate samples.

## 1.0.3 - 2026-05-03

### Added

- **Tests:** **`tests/test_ledger.py`** — MEDIUM vs **`require_high_diff_confidence`**, LOW sample-floor boundary, **`max_latency_ms`** (and skip when latency absent), **`max_error_rate`**, multiple simultaneous policy failure reasons; **`tests/test_spine.py`** — MEDIUM confidence blocks second **`release promote`**, **`runs ingest`** on empty file / malformed JSONL / JSON array payload, **`release diff`** across different pricing providers and across different models on one provider table (plus **`POST /v1/diff`** `pricing.pricing_or_model_changed` assertion).
- **Web UI:** structured **Promote & rollback** outcome (policy badge, pointer status, action/release/baseline IDs, reason list) with raw response in a collapsed **`JsonPanel`**; **Run diff** shows a pricing/model-change callout when **`pricing.pricing_or_model_changed`** is true.

### Changed

- **Roadmap:** **Phase 0 progress** subsection and **Next release** pointer for **v1.0.3**; docs aligned with the patch scope above.

## 1.0.2 - 2026-05-02

### Added

- **CLI:** **`flightdeck release diff --fail-on-policy`** exits **1** when the active policy does not pass (after printing the diff), for CI gates without calling **`release promote`**.
- **HTTP `GET /health`:** response includes **`mutation_auth`** (`loopback` or `bearer`) — safe hint for whether **`FLIGHTDECK_LOCAL_API_TOKEN`** is configured (no secret material).
- **Web UI:** security status strip (server mode + whether **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** is set); optional read-only mode via **`VITE_FLIGHTDECK_UI_READ_ONLY=true`** (hides Promote nav and **`#/actions`**).
- **examples/ci:** **`ledger_gate.py`**, **`ledger-gate-policy.yaml`**, **`ledger-gate.sh`** (wrapper), **`github-actions/policy-gate-*.yml`**, **[examples/ci/README.md](examples/ci/README.md)**; **`.github/workflows/ci.yml`** runs **`uv run python examples/ci/ledger_gate.py`** on **Ubuntu** and **Windows** (no bash-only gate).
- **examples/deploy:** reference **`Dockerfile`**, **`docker-compose.yml`**, **`entrypoint.sh`**, **[examples/deploy/README.md](examples/deploy/README.md)**.
- **examples/integration:** **`emit_sample_events.py`**, **[examples/integration/README.md](examples/integration/README.md)**.
- **Tests:** **`tests/test_server_health.py`**; **`test_release_diff_fail_on_policy_exits_1`** in **`tests/test_cli_contract.py`**; Playwright smoke asserts **`/health`** includes **`mutation_auth`**.

### Fixed

- **`diff_releases` zero policy sample thresholds:** `Policy.min_candidate_runs`, `Policy.min_baseline_runs`, and `Policy.min_low_runs` set to **`0`** now correctly override workspace config defaults to `0` instead of being silently ignored. Previously, `or`-based fallback treated `0` as falsy and fell back to the config value (typically `500` / `50`). Fixed by using explicit `is not None` checks. A policy can now unconditionally accept any sample size by setting thresholds to `0` — for example, to allow diffs over empty event windows without a confidence downgrade.
- **examples/ci ledger gate:** **`ledger_gate.py`** invokes the CLI as **`python -m flightdeck.cli.main`** (avoids nested **`uv run`** / Windows **`flightdeck.exe`** locks); wipes **`WORKSPACE`** with **`shutil.rmtree`** before **`init`**; unique **`WORKSPACE`** per CI run (**`run_id`** + **`run_attempt`**). **`ledger-gate-policy.yaml`** caps cost high enough for quickstart candidate rollup (quickstart **`policy.yaml`** at \$4 rejects **~\$5/run** under **`--fail-on-policy`**).

### Changed

- **Docs:** **`docs/cli.md`** documents **`--fail-on-policy`**; **`docs/http-api.md`** / **`docs/sdk.md`** document **`GET /health`** `mutation_auth`.
- **`.gitattributes`:** LF for **`examples/deploy/*.sh`** (Docker entrypoint) and **`examples/ci/*.sh`** (CI shell wrappers).

## 1.0.1 - 2026-05-01

### Added

- **`.gitattributes`:** force **LF** for **`tests/fixtures/golden_bundle/`** so checkout line endings do not change the pinned bundle digest (matches the **0.7.0** changelog intent).

### Changed

- **Slim distribution:** this repository ships a focused in-tree **`docs/`** tree (CLI, HTTP API, SDK, operations/policy, release artifact, web UI references); org mirror scripts and **`verify-repo-standards`** wrappers are not included. Extended maintainer runbooks and the canonical README live on **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)**; in-repo links now point there where applicable.
- **`pyproject.toml`:** OpenTelemetry packages are **optional** only (**`telemetry`** / **`all`** extras); the default install matches the **1.0.0** dependency story (core does not import OpenTelemetry).
- **`.pre-commit-config.yaml`:** **ruff** replaces **black** / **isort**; **`ruff-pre-commit`** pinned to **v0.15.12** to match **`dev`** (**`ruff==0.15.12`**).
- **CI:** Python **3.13** and **3.14** added to the Ubuntu and Windows matrices (superseded by **3.14**-only policy as of **1.0.2**, then relaxed to **3.11+** as of **1.2.0**).
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

- **[docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md)**: CLI reference (synopsis, flags, exit codes, pointers to quickstart examples).
- **`scripts/quickstart_smoke.py`**: cross-platform quickstart smoke (**no bash**): temp workspace, Python placeholder substitution, **`release verify`**, **`doctor`**.
- **CI:** run quickstart smoke on **Ubuntu** and **Windows** matrix jobs (alongside pytest and schema drift).
- **Tests:** `tests/test_quickstart_smoke.py` exercises the smoke script.
- **0.8 milestone planning** (CLI + CI): archived under **`docs/reviews/`** in development clones; shipped CLI narrative is **[docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md)** on the canonical repo; this tree ships **`scripts/quickstart_smoke.py`** / **`flightdeck-quickstart-verify`** (see **Unreleased**).

### Changed

- **[docs/quickstart.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/quickstart.md)**: recommend **`python scripts/quickstart_smoke.py`** on Windows; bash flow kept as optional.
- **[docs/architecture.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/architecture.md)**: deferred section updated for shipped SDK / rollback / serve / doctor / verify.
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

- **README** / **[docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)** / **[docs/git-remotes.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/git-remotes.md):** point at **`https://github.com/flightdeckdev/flightdeck`**.

## 0.5.1 - 2026-04-30

### Added

- **`flightdeck doctor`**: read-only checks for **SQLite schema migrations** (through `LATEST_SCHEMA_MIGRATION_VERSION`) and **promoted release pointers** (each `promoted_releases.release_id` exists in `releases`).
- **`flightdeck.storage`**: `list_applied_migrations()`, `list_promoted_pointers()`, and **`LATEST_SCHEMA_MIGRATION_VERSION`** (keep in sync when adding migrations).

## 0.5.0 - 2026-04-30

### Added

- **[docs/v1-next-steps.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/v1-next-steps.md)**: Maintainer v1 gap analysis (P0/P1/P2), milestone sequencing (0.5–1.0), and risk callouts; tracks implementation status as work lands.
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

- **[docs/git-remotes.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/git-remotes.md)**: configure **`origin`** (personal research) vs **`org`** ([flightdeckdev](https://github.com/flightdeckdev) canonical), with everyday `git push` examples.

### Changed

- **Research workflow docs** ([docs/research-workflow.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/research-workflow.md), [RESEARCH.md](https://github.com/flightdeckdev/flightdeck/blob/main/RESEARCH.md), [AGENTS.md](AGENTS.md), [.cursorrules](.cursorrules), [docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)) now state explicitly: **personal account** = research clone; **org** = user-facing canonical.

## 0.4.1 - 2026-04-30

### Added

- **[docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)** for the **[flightdeckdev](https://github.com/flightdeckdev)** org: when to add repos, pre-push checklist, private-file policy.
- **`scripts/verify-repo-standards.sh`** / **`.ps1`**: run ruff + pytest before pushing.

### Changed

- **`.gitignore`**: ignore **`.flightdeck/`** (local DB/config), **`private/`**, **`secrets/`**, common cert/credential patterns, **`Thumbs.db`**.
- **Release bundle checksum** moved to **`flightdeck.bundle`**: LF normalization for text-like extensions so CRLF vs LF does not change the digest; `.git` / `__pycache__` under a bundle are excluded from hashing.
- **SQLite migration 2**: index on `run_events(release_id, timestamp)` for ledger queries.

### Security / hygiene

- **[SECURITY.md](SECURITY.md)** and **[CONTRIBUTING.md](CONTRIBUTING.md)** expanded with secret/local-path guidance and link to the org push gate doc.

## 0.4.0 - 2026-04-30

### Added

- **Forward v1 specification** ([docs/spec-v1-forward.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md)): normative direction for v1 GA (versioning, migrations, bundle checksum canonicalization, trust boundaries, diff/policy defaults, SDK testing discipline). [`docs/spec.md`](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec.md) remains the frozen 0.x implementation narrative; new guarantees land here first.
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
