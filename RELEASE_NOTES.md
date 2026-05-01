# Release notes (maintainer)

High-level notes for **shipping FlightDeck**. Detailed history: **[CHANGELOG.md](CHANGELOG.md)**. Contract direction: **[docs/spec-v1-forward.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md)**. Backlog and milestone status: **[docs/v1-next-steps.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/v1-next-steps.md)**.

Narrative docs (including the CLI reference) are maintained on **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** `main`; this file and **`schemas/`** ship in minimal clones.

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

- **CLI** — commands, flags, and exit codes as documented in **[docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md)** (including **`release verify`** exit **2** on checksum mismatch).
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
