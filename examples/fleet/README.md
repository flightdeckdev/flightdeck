# Multi-workspace operator patterns

FlightDeck is **local-first**: one `flightdeck.yaml` + SQLite database per working directory. “Fleet” ergonomics here means **repeatable layouts** and naming—not a hosted control plane.

## Recommended layout

- One directory per environment or product slice, each with its own `flightdeck.yaml` and `.flightdeck/flightdeck.db`.
- Pin `db_path` per workspace (default `.flightdeck/flightdeck.db` is fine if directories never merge).
- Use consistent `default_environment` values (`staging`, `prod`) across repos that feed the same promotion gates.

## Optional pricing catalog

For cross-vendor **comparable** cost lines on `release diff` / `POST /v1/diff`, add `pricing_catalog_path` in `flightdeck.yaml` pointing at a `PricingCatalog` YAML (see `examples/pricing/catalog.sample.yaml`).

## Human approval for promote

Set `promotion_requires_approval: true` in `flightdeck.yaml` to require `release promote-request` / `release promote-confirm` (or HTTP `POST /v1/promote/request` + `POST /v1/promote/confirm`) instead of a direct `release promote`.

## Template

See `workspace-staging.example.yaml` for a copy-paste starting point; copy to your repo root as `flightdeck.yaml` and edit paths.

## Multi-workspace aggregation (read-model)

Prefer **per-workspace** ledgers and **pull**-based joins in your own tooling:

- **`flightdeck runs export`** / **`GET /v1/runs`** (and **`GET /v1/runs/export`** when using `flightdeck serve`) — JSONL or JSON per workspace.
- **`GET /v1/metrics`** — coarse counters per workspace.
- **CI** — one job per workspace directory (see [examples/ci/README.md](../ci/README.md)).
