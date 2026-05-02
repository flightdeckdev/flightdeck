# Pricing catalog (operator YAML)

FlightDeck can load an optional **operator-defined** [`PricingCatalog`](../schemas/v1/pricing_catalog.schema.json) YAML
referenced by **`pricing_catalog_path`** in [`flightdeck.yaml`](release-artifact.md#workspace-config-flightdeckyaml).

## Purpose

Imported **pricing tables** (`flightdeck pricing import …`) drive per-model token rates for runs that match the table’s
**`provider`** + **`pricing_version`**. A **catalog** adds **cross-vendor comparable** rows on diffs (`pricing.catalog` on
`POST /v1/diff` / `release diff`) and diagnostics in **`pricing.hints`** when multiple pricing table versions or naming
patterns appear in the evidence window.

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
