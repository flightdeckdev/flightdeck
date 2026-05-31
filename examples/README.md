# Examples index

This folder holds **copy-pasteable** references for wiring FlightDeck into a real loop: emit evidence, ingest, diff, gate in CI, promote, and run the local HTTP server. Narrative CLI and trust-boundary docs live on the [canonical repository](https://github.com/flightdeckdev/flightdeck) `main`; see also [RELEASE_NOTES.md](../RELEASE_NOTES.md) in this tree.

## End-to-end loop

1. **Emit run events** from your app or a test harness — see [integration/](integration/README.md) (`emit_sample_events.py` and `POST /v1/events` shape). Optional framework-oriented emitters: [integration/adoption/](integration/adoption/README.md).
2. **Ingest** evidence: `flightdeck runs ingest <file.jsonl>` (or JSON array file), or HTTP `POST /v1/events` while `flightdeck serve` is running.
3. **Register** a release bundle: `flightdeck release register <bundle-dir>` then **`flightdeck release verify`** against the same tree before you trust the checksum.
4. **Diff and gate** in CI: `flightdeck release diff …` with **`--fail-on-policy`** when you want a non-zero exit without mutating promotion — see [ci/](ci/README.md) and `ledger_gate.py` / GitHub Actions templates. Optional **`pricing_catalog_path`** in `flightdeck.yaml` adds **`pricing.catalog`** / **`pricing.hints`** on diffs (see [docs/pricing-catalog.md](../docs/pricing-catalog.md)). **Same contract in the browser or HTTP:** with `flightdeck serve`, open **`/#/diff`** for structured policy / pricing / rollup sections, or call **`POST /v1/diff`** (matches **`flightdeck release diff --output json`**). Details: [docs/web-ui.md](../docs/web-ui.md), [docs/http-api.md](../docs/http-api.md).
5. **Promote or rollback** via CLI (`flightdeck release promote` / `rollback`) or HTTP `POST /v1/promote` and `POST /v1/rollback` (token + loopback rules apply). When **`promotion_requires_approval: true`**, use **`release promote-request`** / **`promote-confirm`** or **`POST /v1/promote/request`** then **`POST /v1/promote/confirm`** — see [ci/promote_with_approval.sh](ci/promote_with_approval.sh) and [ci/README.md](ci/README.md) (GitHub Actions patterns).
6. **Run the server** in a container or compose stack — see [deploy/](deploy/README.md). The bundled UI calls **`GET /v1/workspace`** to choose direct promote vs request/confirm.
7. **Triage runs** with **`flightdeck runs list`** / **`runs export`** or **`GET /v1/runs`**, and **observe** aggregate ledger size with **`GET /v1/metrics`** (JSON counters; read-only, same access tier as other `GET /v1/*` routes). With **`flightdeck serve`**, **`/#/runs`** adds optional **Group by trace_id** (collapsible sections) on top of the same API slice.

**UI polish / operator flow:** See [docs/web-ui.md](../docs/web-ui.md) for routing and surfaces. In the bundled app, prefer **Diff** for policy and pricing conclusions, **Runs** for trace-scoped triage, and **Actions** for promote and rollback so operators rarely need raw JSON first.

## Readiness checklist (quick pass)

Use this as a **discoverability** pass for the **[ROADMAP.md](../ROADMAP.md)** success and readiness signals (not a product guarantee):

| Signal | Where to start |
|--------|----------------|
| **Approval-gated promote in CI** | [ci/promote_with_approval.sh](ci/promote_with_approval.sh), [ci/README.md](ci/README.md), [ci/github-actions/promote-approval-twostep.yml](ci/github-actions/promote-approval-twostep.yml) |
| **Two-provider (or catalog) pricing on a diff** | [docs/pricing-catalog.md](../docs/pricing-catalog.md); tests **`test_diff_cross_provider_releases`** and **`test_catalog_comparable_cost_on_cross_provider_diff`** in `tests/` |
| **Operate `flightdeck serve` with deployment guidance** | [deploy/README.md](deploy/README.md) (**Compose healthcheck**, **`restart: unless-stopped`**, **`FLIGHTDECK_LOCAL_API_TOKEN`**, **SQLite backup** via **`flightdeck doctor --backup`**, operator checklist); optional **Helm** under [deploy/chart/flightdeck/](deploy/chart/flightdeck/) |

## Subfolders

| Path | Purpose |
|------|---------|
| [quickstart/](quickstart/) | Minimal workspace used by `flightdeck-quickstart-verify`. |
| [ci/](ci/README.md) | Policy gate script, sample policy YAML, GitHub Actions job snippets. |
| [deploy/](deploy/README.md) | Dockerfile and compose for `flightdeck serve`; optional **Railway** (`railway.toml`). |
| [integration/](integration/README.md) | Sample event emitter for HTTP ingest. |
| [integration/adoption/](integration/adoption/README.md) | OpenAI, Anthropic, LangChain, Agents SDK, CrewAI-style totals, Temporal labels → `RunEvent`. |
| [fleet/](fleet/README.md) | Multi-workspace naming, optional catalog path, approval workflow notes. |
| [pricing/catalog.sample.yaml](pricing/catalog.sample.yaml) | Sample `PricingCatalog` for cross-vendor comparable diff costs. |
