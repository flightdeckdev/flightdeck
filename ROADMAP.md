# Roadmap

## Now

- Local release registry
- Run event ingestion from JSONL/JSON arrays
- Trusted release diff
- Immutable pricing tables (with import audit log)
- Policy-gated promotion
- Promotion history
- Local HTTP ingestion (`flightdeck serve`)
- Rollback command (`flightdeck release rollback`)

## Next (post-1.0 — see **[docs/v1-next-steps.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/v1-next-steps.md)**)

- **v1.0.0 — shipped:** SemVer-stable CLI + **`schemas/v1/`** + **`POST /v1/events`** **`v1`**; **[RELEASE_NOTES.md](RELEASE_NOTES.md)**; **[docs/spec-v1-forward.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md)**.
- **Prior milestones — shipped:** **0.6** (**`audit_seq`**, **`doctor`**), **0.7** (**`release verify`**, golden bundle, CI schema drift), **0.8** ([docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md), **`quickstart_smoke.py`**), **0.9** (HTTP **`api_version`** tests, JSON fixtures, maintainer release notes).
- JSON Schemas: optional expansion of golden fixtures + explicit **schema compatibility** policy text as the surface grows.
- Expand SDK: retries, batching, optional async client ([spec-v1-forward](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md) §6).

Normative direction: **[docs/spec-v1-forward.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md)** · backlog: **[docs/v1-next-steps.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/v1-next-steps.md)** · **canonical publish / staging** (full maintainer runbook): **[docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)** · **[docs/spec.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec.md)** remains the 0.x implementation narrative snapshot.

## Later

- Hosted control plane
- Dashboard
- OpenTelemetry import/export mapping
- Tool-cost pricing
- Enterprise controls
