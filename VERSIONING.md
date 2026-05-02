# Versioning

FlightDeck uses package versions and schema versions separately.

## Package Versions

Package releases use [Semantic Versioning](https://semver.org/).

From **`v1.0.0`**, documented CLI behavior (**[README.md](https://github.com/flightdeckdev/flightdeck/blob/main/README.md)**), committed **`schemas/v1/`**, and
**`POST /v1/events`** **`api_version` `v1`** payloads are **stable public contracts** except when a
**major** release explicitly documents a break. Breaking changes must appear in
**[CHANGELOG.md](CHANGELOG.md)** and, when user-visible, **[RELEASE_NOTES.md](RELEASE_NOTES.md)**.

## Schema Versions

Public payloads include `api_version`.

- Additive fields can remain on the same `api_version`.
- Renames, removals, or semantic changes require a new schema version.
- Unknown required schema versions should fail with actionable errors.

## Database Migrations

Local SQLite uses **explicit numbered migrations** (see `flightdeck.storage` and
`LATEST_SCHEMA_MIGRATION_VERSION`). New schema steps must ship with a migration number,
tests where behavior changes, and **`doctor`** / docs updated when invariants change
(e.g. `audit_seq` in 0.6.0).

Hosted or multi-user operation remains out of scope for the default local spine; migrations
are still the mechanism for evolving the on-disk schema safely.

## Stable contracts (v1.0.0)

The **v1.0.0** freeze is summarized in **[RELEASE_NOTES.md](RELEASE_NOTES.md)**; milestone status lives in **[ROADMAP.md](ROADMAP.md)**.

## PyPI packages

The **PyPI** distribution is **`flightdeck-ai`** (same **SemVer** as **`pyproject.toml`**). The CLI command remains **`flightdeck`**; Python imports remain **`flightdeck.*`**. Publishing is **tag-driven** (push **`v*.*.*`**) via **`.github/workflows/release-pypi.yml`** — see **`DEVELOPMENT.md`** and **`RELEASE_NOTES.md`** (PyPI / GitHub releases).
