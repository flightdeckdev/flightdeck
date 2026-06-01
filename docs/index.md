# FlightDeck

**Ship AI agents safely** — release diffs, runtime evidence, and policy gates.

FlightDeck is a local-first CLI + SQLite + optional web UI that versions your agent builds, collects runtime evidence (cost, latency, errors), diffs a baseline against a candidate, and blocks promote until policy passes. Apache-2.0.

---

## Try it — 30 seconds, no account needed

```bash
pip install flightdeck-ai
flightdeck demo
```

`flightdeck demo` runs the full register → ingest → diff → promote loop in a temporary workspace. Nothing leaves your machine.

---

## How it works

1. **Register** an immutable release snapshot (`release.yaml` + checksum).
2. **Ingest** runtime evidence from your agent (cost, latency, errors, confidence).
3. **Diff** baseline vs candidate — cost per run, latency delta, error rate, pricing catalog.
4. **Promote** only when policy passes; optional human approval before the ledger moves.

The same contract works from the CLI, the HTTP API (`POST /v1/promote`), and the bundled web UI (`flightdeck serve`).

---

## Where to start

| I want to… | Go here |
|---|---|
| Try it in 30 seconds | `pip install flightdeck-ai && flightdeck demo` |
| Wire it to my real agent | [Getting started](getting-started.md) |
| See all CLI commands | [CLI reference](cli.md) |
| Use the HTTP API | [HTTP API](http-api.md) |
| Understand policy gates | [Operations & policy](operations-and-policy.md) |
| Self-host `flightdeck serve` | [HTTP API — starting the server](http-api.md#starting-the-server) |
| Deploy for a team in production | [Getting started → Production checklist](getting-started.md#production-checklist) |
| Something broke | [Troubleshooting](troubleshooting.md) |

---

## Quick reference

| Topic | Doc |
|--------|-----|
| Commands, flags, exit codes | [CLI reference](cli.md) |
| `flightdeck serve` JSON API | [HTTP API](http-api.md) |
| Diff, promote, rollback, SQLite | [Operations & policy](operations-and-policy.md) |
| `release.yaml`, workspace config | [Release artifact](release-artifact.md) |
| Optional pricing catalog YAML | [Pricing catalog](pricing-catalog.md) |
| `flightdeck` Python client | [Python SDK](sdk.md) |
| Experimental adoption hooks | [SDK integrations](sdk-integrations.md) |
| Shipped web UI vs roadmap | [Web UI](web-ui.md) · [UI roadmap](ui-roadmap.md) |
| Common failures | [Troubleshooting](troubleshooting.md) |

Full examples and CI templates: [github.com/flightdeckdev/flightdeck/examples](https://github.com/flightdeckdev/flightdeck/tree/main/examples)

---

## Who should use this?

- **ML / platform engineering** teams shipping LLM agents to production who want a policy-gated promote path — not just a dashboard.
- **Regulated or compliance-sensitive** teams (fintech, healthcare) where data residency and audit trails matter. Local-first by default; self-host `flightdeck serve` to keep data on-prem.
- Engineers who want to answer "is this candidate safe to ship?" with **numbers and policy**, not gut feel.

---

## Install options

**User (recommended):**

```bash
pip install flightdeck-ai
```

Optional extras: `flightdeck-ai[openai]`, `flightdeck-ai[anthropic]`, `flightdeck-ai[postgres]`, `flightdeck-ai[telemetry]`

**Contributor (uv):**

```bash
git clone https://github.com/flightdeckdev/flightdeck
cd flightdeck
uv sync --extra dev
uv run flightdeck --help
```

See [DEVELOPMENT.md](https://github.com/flightdeckdev/flightdeck/blob/main/DEVELOPMENT.md) for web bundle, schema generation, and CI parity.

---

## Ask AI

Use the floating **Ask AI** button (bottom-right) to open Perplexity with this docs site and the GitHub repo as context. No FlightDeck servers are involved.
