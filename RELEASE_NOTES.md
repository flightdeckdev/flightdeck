# Release notes (maintainer)

High-level notes for **shipping FlightDeck**. Detailed history: **[CHANGELOG.md](CHANGELOG.md)**. Backlog and milestone status: **[ROADMAP.md](ROADMAP.md)**.

Narrative docs (including the CLI reference) are maintained on **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** `main`; this file and **`schemas/`** ship in minimal clones.

## Unreleased (in development)

- **Bundled pricing hygiene:** **`flightdeck pricing check`** reports **`flightdeck-bundled-*`** snapshot age vs **`--max-age-days`** (default **90**); **`--fail`** exits non-zero for CI. **`release diff`** / **`POST /v1/diff`** append **`pricing.warnings`** for the same staleness rule so cost signals do not go silently wrong. Bundled YAML gains vendor **official pricing** URL comments; docs and **ROADMAP** state a **minor-release refresh** cadence for the bundled snapshot when list prices move materially.
- **Contributor tooling:** **`[project.optional-dependencies] dev`** uses **`ruff>=0.15,<0.16`** (see **`CHANGELOG.md`**).
- **Telemetry extra:** optional **`flightdeck.integrations.telemetry.configure_otel_tracing()`** wires OTLP span export to **your** backend (see **`docs/sdk-integrations.md`**).

## v1.2.0 — Python 3.11+, protected ingest and reads, bundled pricing, Postgres, integrations

Minor release (see **[CHANGELOG.md](CHANGELOG.md)** for the full list).

- **Python floor:** **`requires-python`** is **`>=3.11,<4`** so installs work on common production interpreters (**3.11–3.14**). **`[tool.ruff] target-version`** is **`py311`**.
- **HTTP / trust:** **`POST /v1/events`** is a **ledger write** and matches the promote/rollback access model: **loopback-only** when **`FLIGHTDECK_LOCAL_API_TOKEN`** is unset; **Bearer required** when it is set. When a token is set, **`GET /v1/*`** read APIs require the same **Bearer** header (previously only mutations were gated). **`POST /v1/diff`** stays read-only and ungated. **`GET /health`** adds **`read_auth`** (`open` vs `bearer`). **Migration:** remote emitters must send **`Authorization: Bearer`** whenever the server uses a local API token; loopback scripts without a token are unchanged.
- **`flightdeck init`:** by default seeds **bundled** OpenAI / Anthropic / Google (**`google`** = Gemini-class) pricing at **`flightdeck-bundled-2026-05`**, writes **`.flightdeck/pricing-catalog.yaml`**, and sets **`pricing_catalog_path`** (additive for **new** workspaces). **`flightdeck init --no-bundled-pricing`** restores config-only init.
- **Ledger backends:** optional **`database_url`** (**PostgreSQL**) with **`psycopg`** extra; SQLite busy retries and **`flightdeck serve`** SQLite tuning flags.
- **Evidence / UI:** **`GET /v1/runs/export`**, **`session_id`** / **`span_id`** filters and **`offset`** on run listings; bundled **Web Runs** page and substantial **Runs / Diff / Actions / shell** UX improvements (see changelog).
- **Experimental `flightdeck.integrations`:** optional **`integrations-*`** extras and CI **`integrations`** job; **`RunEvent`** wire shape unchanged — adapters are adoption glue per **`AGENTS.md`**.
- **Quality:** **`pytest-cov`** with **`--cov-fail-under=80`** on core **`flightdeck`**; Playwright **`e2e-server.mjs`** uses **`init --no-bundled-pricing`** for stable default **`GET /v1/workspace`** expectations.

**Stable contracts:** breaking items are the **Python range**, **ingest + read Bearer** rules when a token is set, and the new **default init** workspace layout; HTTP and **`v1`** payload shapes remain additive aside from those access changes.

## v1.1.2 — Forensics filters, JSONL export, productization closure slice

Patch release (see **[CHANGELOG.md](CHANGELOG.md)**): optional **`trace_id`** filter on **`GET /v1/runs`**, **`flightdeck runs list --trace-id`**, and SDK **`list_runs(trace_id=…)`** (exact match on **`RunEvent.request.trace_id`**); **`flightdeck runs export`** writes the same filtered slice as JSONL (stdout or **`-o`**, **`--limit`** up to **500**, stderr warning when truncated). **Stable contracts:** additive HTTP query param and CLI command only.

## v1.1.1 — Workspace discovery, web approval UX, docs + CI cookbook

Patch release (see **[CHANGELOG.md](CHANGELOG.md)**): **`GET /v1/workspace`** exposes non-secret workspace flags (**`promotion_requires_approval`**, **`pricing_catalog_configured`**, **`server_version`**) for scripting and the **Actions** page; web **Promote** follows the two-step request/confirm path when approval is required; expanded operator docs and **`examples/ci/promote_with_approval.sh`** + README workflow snippet. **Stable contracts:** additive HTTP and JSON Schema only.

## v1.1.0 — Catalog, approval, runs, Helm, fleet (first v1.1 slice)

Minor release (see **[CHANGELOG.md](CHANGELOG.md)**): optional **`pricing_catalog_path`** + **`PricingCatalog`** YAML for cross-vendor comparable **`pricing.catalog`** lines on diffs; **`pricing.hints`** for multi-version and model-name diagnostics; **`promotion_requires_approval`** with **`POST /v1/promote/request`** / **`POST /v1/promote/confirm`** / **`GET /v1/promotion-requests`** and matching CLI; **`GET /v1/runs`** and **`flightdeck runs list`**; SQLite migration **v4** (`promotion_requests`); reference **Helm** chart and **fleet** docs under **`examples/`**. **Stable contracts:** additive HTTP and CLI surfaces; existing **`v1`** event and release payloads unchanged.

## v1.0.6 — Phase 0 closure (backup, cross-language emitters, roadmap)

Patch release (see **[CHANGELOG.md](CHANGELOG.md)**): **`flightdeck doctor --backup PATH`** performs a SQLite online backup of the workspace DB; **[examples/integration/](examples/integration/README.md)** gains **`curl`** and a **Node** **`emit_sample_events.node.mjs`** path for **`POST /v1/events`**; **[examples/deploy/README.md](examples/deploy/README.md)** documents the Compose **`/health`** healthcheck and backup scheduling. **ROADMAP:** **Phase 0** is **closed**; **catalog-level** multi-provider pricing normalization is an explicit **mid-term** build item. **Stable contracts:** additive CLI flag and HTTP field **`pricing.warnings`** (from **v1.0.5**) remain backward-compatible.

## v1.0.5 — Diff JSON output, pricing warnings, metrics in Overview

Patch release (see **[CHANGELOG.md](CHANGELOG.md)**): **`flightdeck release diff --output json`** matches **`POST /v1/diff`** for machine consumers; **`pricing.warnings`** surfaces missing pricing-table rows for a release's resolved model (CLI **`WARNING:`** lines + web); **Overview** shows **`GET /v1/metrics`** counters. **Stable contracts:** additive only.

## v1.0.4 — Phase 0 closing slice (pricing diagnostic, examples index, metrics)

Patch release (see **[CHANGELOG.md](CHANGELOG.md)**): **`GET /v1/metrics`** exposes additive JSON counters for operators; **`POST /v1/diff`** and **`flightdeck release diff`** add **`pricing.prices`** / a **Per-1k token prices** line when pricing or model differs, so cost deltas are easier to interpret; **[examples/README.md](examples/README.md)** ties **integration**, **CI**, and **deploy** examples into one loop; web **Run diff** shows the same unit-price deltas when present. **Stable contracts:** additive HTTP and CLI output only; no **`v1`** payload or schema removals.

## v1.0.3 — Phase 0 hardening (tests + UI)

Patch release (see **[CHANGELOG.md](CHANGELOG.md)**): broader **pytest** coverage for **`diff_releases`** (MEDIUM/LOW confidence, **`max_latency_ms`**, **`max_error_rate`**, combined failures), **CLI** integration for MEDIUM confidence blocking promotion when **`require_high_diff_confidence`** is on, **`runs ingest`** edge cases (empty file, bad JSONL, JSON array file), and **multi-provider / cross-model** **`release diff`** plus **`POST /v1/diff`** parity on **`pricing.pricing_or_model_changed`**. **Web UI:** promote/rollback responses use structured panels (raw JSON optional); **Run diff** surfaces the same pricing/model-change note as the CLI when the diff payload flags it. **Stable contracts:** no CLI flag removals, no **`v1`** schema or **`POST /v1/events`** shape changes; **HTTP** diff and action response shapes are unchanged (additive UI only on the client).

## v1.0.2 — CI examples, serve packaging, and policy gate CLI

Minor release (see **[CHANGELOG.md](CHANGELOG.md)**): **`flightdeck release diff --fail-on-policy`** for CI gates; **`examples/ci/`** (`ledger-gate.sh`, GitHub Actions templates) exercised in root CI; **`examples/deploy/`** (Docker/Compose for **`flightdeck serve`**); **`examples/integration/`** (SDK sample emitter for **`POST /v1/events`**); **`GET /health`** adds non-secret **`mutation_auth`** (`loopback` vs `bearer`); web shell shows mutation/token ergonomics and optional read-only UI (**`VITE_FLIGHTDECK_UI_READ_ONLY`**). Fix: policy **`min_*_runs`** explicit **`0`** overrides workspace defaults ( **`is not None`** resolution in **`diff_releases`** ). **Stable contracts:** additive **`/health`** field only; CLI flag is backward-compatible.

## v1.0.1 — distribution and developer tooling

Patch release (see **[CHANGELOG.md](CHANGELOG.md)**): canonical **`main`** URLs for narrative docs in slim clones, optional OpenTelemetry in extras only, CI on **CPython 3.14** (Ubuntu and Windows), repo-local **pytest** basetemp on Windows, **ruff** pinned consistently with **pre-commit**, **`.gitattributes`** LF for the golden bundle fixture, and removal of a test that depended on unpublished export scripts. **Public CLI / schema / HTTP contracts** are unchanged from **v1.0.0**.

## PyPI and GitHub releases

- **Not automatic on merge:** publishing runs when a **SemVer tag** matching **`vMAJOR.MINOR.PATCH`** is pushed (see **`.github/workflows/release-pypi.yml`**).
- **PyPI project:** **`flightdeck-ai`** (matches **`[project] name`** in **`pyproject.toml`**). **Trusted publishing** (OIDC) — no **`PYPI_API_TOKEN`** in repo secrets; register workflow **`release-pypi.yml`** on the project. If PyPI shows **Environment name: (Any)**, you do not need to match a specific string there; the workflow still uses GitHub **Environment** **`pypi`** for optional approval gates.
- **Checks before upload:** same bar as CI (**ruff**, **pytest**, schema drift) plus a **tag ↔ `pyproject.toml` version** match.
- **GitHub:** the workflow creates a **Release** for the tag with **generated notes** and attaches **`dist/*`**.

Details: **`DEVELOPMENT.md`** (PyPI release section).

## v1.0.0 — stable public contracts

**v1.0.0** freezes the following unless a future **major** release says otherwise:

- **CLI** — commands, flags, and exit codes as documented in **[README.md](https://github.com/flightdeckdev/flightdeck/blob/main/README.md)** (including **`release verify`** exit **2** on checksum mismatch).
- **JSON Schemas** — committed **`schemas/v1/`** for **`api_version` `v1`** payloads; regenerate via **`python scripts/generate_schemas.py`**; CI guards drift.
- **HTTP** — **`POST /v1/events`**, envelope **`{ "events": [ … ] }`**, per-event **`api_version`** omitted or **`"v1"`**; rejects other values with **HTTP 400** and the stable **`detail`** format covered by tests.
- **SQLite** — forward-only numbered migrations; **`flightdeck doctor`** checks migrations and **`audit_seq`** continuity as shipped.

The product remains **local-first**; hosted control plane, OTel mapping, and related items stay on **`ROADMAP.md`**.

Optional OTEL libraries (not used by core today): **`pip install 'flightdeck-ai[telemetry]'`**.

## Python SDK

**`flightdeck.sdk`** ships with the same SemVer as the CLI; CI covers **`flightdeck.sdk.client`** for local ingest helpers. For the strictest stability expectations, prefer the **CLI** and **HTTP** contracts above.

## Trust boundaries (local spine)

- **`flightdeck serve`**: binding to a non-loopback address prints a warning; **there is no HTTP auth** in the default local server — treat network exposure as operator-controlled risk.
- **`flightdeck release verify`**: compares **registered bundle checksum** vs **current directory tree hash**; exit **2** on mismatch (**1** for normal CLI errors).
- **`flightdeck doctor`**: read-only checks for SQLite migrations through **`LATEST_SCHEMA_MIGRATION_VERSION`** and basic **`promoted_releases` ↔ `releases`** consistency; **`audit_seq`** on **`release_actions`** must be contiguous (**0.6.0+**).

## SQLite upgrades

Schema evolves via **numbered migrations**. Existing **`flightdeck.yaml`** / **`.flightdeck/`** trees pick up new migrations on next CLI or **`serve`** startup when **`Storage.migrate()`** runs. If you maintain long-lived local databases, skim **[CHANGELOG.md](CHANGELOG.md)** before upgrading across **minor** versions.

## Semantic versioning (from v1.0.0)

**Patch** — bug fixes and internal refactors that preserve CLI/schema/HTTP contracts.

**Minor** — backward-compatible additions (new optional flags, additive JSON fields within **`api_version` `v1`**, new commands).

**Major** — breaking CLI contracts, breaking **`v1`** payload shapes, or removal of documented behavior. Migration notes belong in **CHANGELOG** and here when relevant.

## Payload versioning

- **`api_version`** on **`RunEvent`** and **`ReleaseArtifact`** is **`"v1"`** for this freeze; **`POST /v1/events`** rejects other values with **HTTP 400** and a stable **`detail`** string (missing key defaults to **`v1`** server-side before validation).
- JSON Schemas under **`schemas/v1/`** are generated — run **`python scripts/generate_schemas.py`** after model changes; CI fails on drift.
