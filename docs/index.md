# FlightDeck documentation

FlightDeck helps teams **ship AI agents safely** with **release diffs**, **runtime evidence**, and **policy gates**.

This site mirrors the Markdown guides in the [flightdeck repository](https://github.com/flightdeckdev/flightdeck). Use the navigation on the left for the full reference. Repository-only pages (for example `SECURITY.md` at the repo root) are linked from the guides where relevant—open those on GitHub when you need the latest wording.

## Ask AI

Use the floating **Ask AI** button in the bottom-right corner to open **Perplexity** in a new tab with this documentation site and the GitHub repo as grounding context (CLI, `release.yaml`, HTTP `/v1` routes, policy). No FlightDeck servers are involved.

## Quick links

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

## Install (local)

```bash
uv sync --extra dev
uv run flightdeck --help
uv run flightdeck-quickstart-verify
```

See [DEVELOPMENT.md](https://github.com/flightdeckdev/flightdeck/blob/main/DEVELOPMENT.md) on GitHub for full contributor setup, web bundle rebuild, and CI parity.
