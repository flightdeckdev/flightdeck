# Pricing catalog (operator YAML)

FlightDeck can load an optional **operator-defined** [`PricingCatalog`](../schemas/v1/pricing_catalog.schema.json) YAML
referenced by **`pricing_catalog_path`** in [`flightdeck.yaml`](release-artifact.md#workspace-config-flightdeckyaml).

## Purpose

Imported **pricing tables** (`flightdeck pricing import …`) drive per-model token rates for runs that match the table’s
**`provider`** + **`pricing_version`**. A **catalog** adds **cross-vendor comparable** rows on diffs (`pricing.catalog` on
`POST /v1/diff` / `release diff`) and diagnostics in **`pricing.hints`** when multiple pricing table versions or naming
patterns appear in the evidence window.

## Bundled snapshot (`flightdeck init`)

Unless you pass **`--no-bundled-pricing`**, **`flightdeck init`** imports three convenience tables
(**`openai`**, **`anthropic`**, **`google`**) at **`pricing_version` `flightdeck-bundled-2026-05`**
(illustrative USD/1k token rates, **not** live vendor APIs). It copies the matching **PricingCatalog**
to **`.flightdeck/pricing-catalog.yaml`** and sets **`pricing_catalog_path`** in **`flightdeck.yaml`**.

Pin **`spec.pricing_reference`** in **`release.yaml`** to **`provider` + `flightdeck-bundled-2026-05`**
for the side you want priced. For **Gemini-class** models, use **`provider: google`** in both the
release runtime and pricing reference. For production accuracy, **`flightdeck pricing import`**
your own YAML (and optionally **`--replace`** with **`--reason`**).

Bundled table YAML in the wheel includes **comment links** to each provider’s official list-pricing page so you can spot-check rates between FlightDeck releases.

**Staleness guardrails:** list prices change often. Run **`flightdeck pricing check`** to see whether any **`flightdeck-bundled-*`** table in the ledger is older than **`--max-age-days`** (default **90**); pass **`--fail`** for CI. **`flightdeck release diff`** and **`POST /v1/diff`** add **`pricing.warnings`** when baseline or candidate **`pricing_version`** is a stale bundled snapshot so economics do not look authoritative after the snapshot has aged out.

**Maintainer cadence:** the bundled snapshot is **updated on each minor release** when vendor public list pricing changes materially (see **[ROADMAP.md](../ROADMAP.md)**). Operators in production should still treat **`flightdeck pricing import`** as the source of truth.

## Relationship to `pricing.prices`

On a diff, **`pricing.prices`** (when present) reflects **per-side imported tables** for the resolved baseline/candidate
models. **`pricing.catalog`** is **additive**: slot/tariff lines from the catalog file, gated by whether the catalog is
enabled and resolvable. You can use **tables only**, **catalog only** for comparable lines, or **both** — they answer
different questions (strict table match vs operator normalization).

## Configuration

Set a non-empty path in `flightdeck.yaml`:

```yaml
pricing_catalog_path: pricing/catalog.yaml
```

Paths are relative to the workspace working directory or absolute. **`GET /v1/workspace`** reports
**`pricing_catalog_configured: true`** when this field is set to a non-empty string (the file is not opened for that probe).

## Failure modes

- **Missing file** — catalog features stay off; diff may note disabled catalog in the payload.
- **Malformed YAML** — syntax errors are treated as **non-fatal** for the diff: the request still returns **HTTP 200** with
  catalog disabled and diagnostics where implemented; see [CHANGELOG.md](../CHANGELOG.md) for behavior on your version.

## Sample

See **[examples/pricing/catalog.sample.yaml](../examples/pricing/catalog.sample.yaml)**.
