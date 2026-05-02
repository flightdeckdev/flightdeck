# Examples index

This folder holds **copy-pasteable** references for wiring FlightDeck into a real loop: emit evidence, ingest, diff, gate in CI, promote, and run the local HTTP server. Narrative CLI and trust-boundary docs live on the [canonical repository](https://github.com/flightdeckdev/flightdeck) `main`; see also [RELEASE_NOTES.md](../RELEASE_NOTES.md) in this tree.

## End-to-end loop

1. **Emit run events** from your app or a test harness — see [integration/](integration/README.md) (`emit_sample_events.py` and `POST /v1/events` shape).
2. **Ingest** evidence: `flightdeck runs ingest <file.jsonl>` (or JSON array file), or HTTP `POST /v1/events` while `flightdeck serve` is running.
3. **Register** a release bundle: `flightdeck release register <bundle-dir>` then **`flightdeck release verify`** against the same tree before you trust the checksum.
4. **Diff and gate** in CI: `flightdeck release diff …` with **`--fail-on-policy`** when you want a non-zero exit without mutating promotion — see [ci/](ci/README.md) and `ledger_gate.py` / GitHub Actions templates. Optional **`pricing_catalog_path`** in `flightdeck.yaml` adds **`pricing.catalog`** / **`pricing.hints`** on diffs (see [docs/pricing-catalog.md](../docs/pricing-catalog.md)).
5. **Promote or rollback** via CLI (`flightdeck release promote` / `rollback`) or HTTP `POST /v1/promote` and `POST /v1/rollback` (token + loopback rules apply). When **`promotion_requires_approval: true`**, use **`release promote-request`** / **`promote-confirm`** or **`POST /v1/promote/request`** then **`POST /v1/promote/confirm`** — see [ci/promote_with_approval.sh](ci/promote_with_approval.sh).
6. **Run the server** in a container or compose stack — see [deploy/](deploy/README.md). The bundled UI calls **`GET /v1/workspace`** to choose direct promote vs request/confirm.
7. **Triage runs** with **`flightdeck runs list`** or **`GET /v1/runs`**, and **observe** aggregate ledger size with **`GET /v1/metrics`** (JSON counters; read-only, same access tier as other `GET /v1/*` routes).

## Subfolders

| Path | Purpose |
|------|---------|
| [quickstart/](quickstart/) | Minimal workspace used by `flightdeck-quickstart-verify`. |
| [ci/](ci/README.md) | Policy gate script, sample policy YAML, GitHub Actions job snippets. |
| [deploy/](deploy/README.md) | Dockerfile and compose for `flightdeck serve`. |
| [integration/](integration/README.md) | Sample event emitter for HTTP ingest. |
| [fleet/](fleet/README.md) | Multi-workspace naming, optional catalog path, approval workflow notes. |
| [pricing/catalog.sample.yaml](pricing/catalog.sample.yaml) | Sample `PricingCatalog` for cross-vendor comparable diff costs. |
