# FlightDeck

FlightDeck is **AI Release Governance** for production agents.

It gives teams a local-first control loop for release safety: register immutable agent
releases, ingest runtime evidence, compare trusted diffs, and gate promotion with policy.

FlightDeck is not an agent framework, prompt IDE, tracing dashboard, or gateway. It is the
operating record for what changed, what it costs, how it behaves, and whether it is safe to
promote.

## Why It Exists

AI agent changes can silently alter cost, latency, failure rate, and unit economics. FlightDeck
turns those changes into explicit release decisions backed by runtime evidence.

Current local spine:

- versioned `release.yaml` artifacts with bundle checksums
- `RunEvent` ingestion from JSONL or JSON arrays
- immutable pricing tables with explicit `--replace`
- trusted `flightdeck release diff`
- policy-gated `flightdeck release promote`
- promotion decision history

## Status

FlightDeck is **local-first** and ships as a Python CLI backed by SQLite.

**v1.0.0** froze **SemVer-stable public contracts** for the documented CLI, committed **`schemas/v1/`**,
and **`POST /v1/events`** with **`api_version` `v1`**. **v1.1.x** adds Phase 1 slices (optional pricing catalog on diffs,
promotion request/confirm, read-only runs listing, **`GET /v1/workspace`** for UI and automation, Helm/fleet examples)
without breaking those v1.0 shapes. See **[RELEASE_NOTES.md](RELEASE_NOTES.md)** and **[CHANGELOG.md](CHANGELOG.md)**.
The product scope is still intentionally narrow (release governance, not a hosted agent platform).

Not implemented yet:

- hosted control plane
- automated traffic routing
- tool-cost pricing
- OpenTelemetry import/export mapping (optional **`uv sync --extra telemetry`** or **`pip install 'flightdeck-ai[telemetry]'`** for future work)

Shipped locally:

- `flightdeck serve` + JSON routes under `/v1/*` (read + diff/promote/rollback + event ingest); see **Local HTTP API** below
- minimal Python SDK (`flightdeck.sdk.client`)
- `flightdeck release rollback` (policy-gated, audited)
- optional **`promotion_requires_approval`** in `flightdeck.yaml` with **`POST /v1/promote/request`** and **`POST /v1/promote/confirm`**

### Local HTTP API

With **`flightdeck serve`** (default bind **127.0.0.1**), the app exposes **`GET /health`**, **`GET /v1/workspace`**
(read-only workspace flags for scripts and the bundled UI), **`GET /v1/metrics`**, **`GET /v1/releases`**, **`GET /v1/promoted`**, **`GET /v1/actions`**, **`GET /v1/promotion-requests`**, **`GET /v1/runs`**, **`POST /v1/events`**, **`POST /v1/diff`**, **`POST /v1/promote`**, **`POST /v1/promote/request`**, **`POST /v1/promote/confirm`**, and **`POST /v1/rollback`**. **`POST /v1/promote`**, **`POST /v1/promote/request`**, **`POST /v1/promote/confirm`**, and **`POST /v1/rollback`** accept requests only from loopback clients unless **`FLIGHTDECK_LOCAL_API_TOKEN`** is set, in which case callers must send **`Authorization: Bearer <token>`** (same behavior as the **`web/`** dev UI via **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`**). See **[docs/http-api.md](docs/http-api.md)** and **[SECURITY.md](SECURITY.md)**.

## Quickstart

Install **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, then from the repo root:

```bash
uv sync --extra dev
uv run flightdeck --help
```

Or with **pip** and a venv:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
flightdeck --help
```

Run the cross-platform quickstart smoke (same as CI):

```bash
uv run flightdeck-quickstart-verify
```

(or **`python -m flightdeck.quickstart_smoke`** / **`python scripts/quickstart_smoke.py`** inside an activated venv)

Or use the bash wrapper (Git Bash / WSL on Windows):

```bash
./scripts/smoke.sh
```

Or walk through the core commands:

```bash
flightdeck init
flightdeck pricing import examples/quickstart/pricing-baseline.yaml
flightdeck pricing import examples/quickstart/pricing-candidate.yaml
flightdeck policy set examples/quickstart/policy.yaml

BASELINE=$(flightdeck release register examples/quickstart/baseline-release)
CANDIDATE=$(flightdeck release register examples/quickstart/candidate-release)

sed "s/__BASELINE_RELEASE_ID__/${BASELINE}/g" examples/quickstart/baseline-events.jsonl > baseline-events.jsonl
sed "s/__CANDIDATE_RELEASE_ID__/${CANDIDATE}/g" examples/quickstart/candidate-events.jsonl > candidate-events.jsonl

flightdeck runs ingest baseline-events.jsonl
flightdeck runs ingest candidate-events.jsonl

flightdeck release diff "$BASELINE" "$CANDIDATE" --window 7d
flightdeck release promote "$BASELINE" --env local --window 7d --reason "initial baseline"
flightdeck release history --agent agent_support --env local
```

The static event files in `examples/quickstart` use placeholder release IDs so the repo can ship stable examples.
Substitute them before ingestion, or run **`uv run flightdeck-quickstart-verify`** / **`python -m flightdeck.quickstart_smoke`** (venv) or **`./scripts/smoke.sh`** from Git Bash/WSL on Windows.

**Examples:** [examples/quickstart/](examples/quickstart/) · [examples/ci/](examples/ci/) (policy gate + Actions) · [examples/deploy/](examples/deploy/) (`serve` via Docker/Compose) · [examples/integration/](examples/integration/) (HTTP event emitter).

## Documentation

- [CLI reference](docs/cli.md) — all commands, flags, arguments, and exit codes
- [HTTP API reference](docs/http-api.md) — all `/v1/*` routes, request/response shapes, auth, `RunEvent` field reference
- [Python SDK](docs/sdk.md) — `FlightdeckClient` / `AsyncFlightdeckClient` usage guide
- [Operations and policy](docs/operations-and-policy.md) — diff, promote, rollback internals; policy model and confidence tiers
- [Release artifacts and pricing](docs/release-artifact.md) — `release.yaml` format, bundle layout, checksum algorithm, workspace config, pricing tables
- [Pricing catalog](docs/pricing-catalog.md) — optional `pricing_catalog_path`, catalog vs imported tables, troubleshooting
- [JSON Schemas](schemas/v1/)
- [Release notes (maintainer)](RELEASE_NOTES.md)
- [Roadmap](ROADMAP.md)
- [Versioning](VERSIONING.md)
- [Development](DEVELOPMENT.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [CLAUDE.md](CLAUDE.md) and [AGENTS.md](AGENTS.md)

## Development

```bash
uv sync --frozen --extra dev
uv run python -m ruff check src tests
uv run python -m pytest
uv run flightdeck-quickstart-verify
uv run flightdeck --help
```

If you change **`web/`** or **Pydantic models**, also run the **`static/`** and **`schemas/`** drift checks from **[DEVELOPMENT.md](DEVELOPMENT.md)** (same gates as **`.github/workflows/ci.yml`**). **[AGENTS.md](AGENTS.md)** and **[`.cursor/rules/flightdeck-ci-artifacts.mdc`](.cursor/rules/flightdeck-ci-artifacts.mdc)** summarize them for humans and Cursor.

See [DEVELOPMENT.md](DEVELOPMENT.md) for **uv** and **pip** setup, verification, troubleshooting, and **PyPI releases** (tag-driven; not on merge to `main`).

## License

FlightDeck is licensed under the **Apache License, Version 2.0** — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

The canonical public repository: [https://github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck).
