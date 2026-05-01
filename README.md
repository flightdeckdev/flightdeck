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

**v1.0.0** establishes **SemVer-stable public contracts** for the documented CLI
(**[docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md)** on `main`),
committed **`schemas/v1/`**, and **`POST /v1/events`** with **`api_version` `v1`**. See
**[RELEASE_NOTES.md](RELEASE_NOTES.md)** and
**[docs/spec-v1-forward.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md)**.
The product scope is still intentionally narrow (release governance, not a hosted agent platform).

Not implemented yet:

- hosted control plane
- automated traffic routing
- tool-cost pricing
- OpenTelemetry import/export mapping (optional **`pip install 'flightdeck[telemetry]'`** pulls deps for future work)

Shipped locally:

- `flightdeck serve` + `POST /v1/events`
- minimal Python SDK (`flightdeck.sdk.client`)
- `flightdeck release rollback` (policy-gated, audited)

## Quickstart

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
flightdeck --help
```

Run the cross-platform quickstart smoke (same as CI):

```bash
python scripts/quickstart_smoke.py
```

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
Substitute them before ingestion, or run **`python scripts/quickstart_smoke.py`** (any OS) or **`./scripts/smoke.sh`** from Git Bash/WSL on Windows.

## Documentation

This tree stays small; narrative docs live on **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)** (`main`):

- [Quickstart](https://github.com/flightdeckdev/flightdeck/blob/main/docs/quickstart.md)
- [CLI reference](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md)
- [Architecture](https://github.com/flightdeckdev/flightdeck/blob/main/docs/architecture.md)
- [Specification (0.x snapshot)](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec.md)
- [Forward spec — v1 GA track](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md)
- [v1 next steps (backlog)](https://github.com/flightdeckdev/flightdeck/blob/main/docs/v1-next-steps.md)
- [JSON Schemas](schemas/v1/) (in this repo)
- [Changelog](CHANGELOG.md)
- [Release notes (maintainer)](RELEASE_NOTES.md)
- [Roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [CLAUDE.md](CLAUDE.md) (short agent entry; see [AGENTS.md](AGENTS.md) for full rules)
- [Development](DEVELOPMENT.md)
- [Security](SECURITY.md)
- [Research clone vs org repos](https://github.com/flightdeckdev/flightdeck/blob/main/docs/research-workflow.md)
- [Git remotes: personal vs org](https://github.com/flightdeckdev/flightdeck/blob/main/docs/git-remotes.md)
- [GitHub org & push gate](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)

## Development

```bash
python -m ruff check src tests
python -m pytest
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for setup, verification, and troubleshooting.

## License

FlightDeck is licensed under the **Apache License, Version 2.0** — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

The canonical public repository: [https://github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck).
