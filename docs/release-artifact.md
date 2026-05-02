# Release Artifacts, Bundles, and Pricing Tables

This document covers the on-disk formats that FlightDeck ingests: the `release.yaml` artifact
schema, bundle directory layout, bundle checksum algorithm, and pricing table YAML format.
For the operations that consume these formats (diff, promote, rollback) see
[operations-and-policy.md](operations-and-policy.md).

---

## `release.yaml` — field reference

`release.yaml` is the single file that describes an immutable agent release.

```yaml
api_version: v1        # required; must be "v1"
kind: Release          # required; must be "Release"
metadata:
  name: support-agent         # required; human label for the release
  version: "2.1.0"            # required; free-form version string
  description: "..."          # optional
  created_by: "ci-bot"        # optional
  created_at: "2026-05-01T12:00:00Z"  # optional ISO-8601
spec:
  agent:
    agent_id: agent_support   # required; stable identifier across releases
    entrypoint: "src/agent.py"  # optional
  runtime:
    provider: openai          # required; e.g. "openai", "anthropic"
    model: gpt-4o             # required; model name used for token cost lookup
    temperature: 0.2          # optional
    max_output_tokens: 800    # optional
  prompts:
    system_ref: prompts/system.md   # required; path relative to bundle root
    template_refs:                  # optional; additional prompt file paths
      - prompts/user.md
  tools:                      # optional
    manifest_ref: tools.yaml  # optional; path to tool manifest
    tool_names:               # optional; list of tool names
      - search
      - calculator
  routing:                    # optional
    strategy: single_model    # "single_model" (default) | "fallback_model"
    fallback:                 # only when strategy is "fallback_model"
      model: gpt-4o-mini
      on_error: true          # trigger fallback on error (default: true)
  safety:                     # optional
    retry_policy:
      max_retries: 2
      backoff_ms: 200         # optional
    timeouts_ms:              # optional
      model_call: 30000
      tool_call: 10000
  pricing_reference:
    provider: openai          # required; must match a loaded pricing table
    pricing_version: "2024-05"  # required; must match a loaded pricing table
  tags:                       # optional; arbitrary key-value strings
    env: production
    team: support
```

All field values are stored verbatim in the `releases` SQLite table as `artifact_json`. The
`spec.agent.agent_id` is the primary grouping key used by diff, promote, and rollback.

**JSON Schema:** [`schemas/v1/release.schema.json`](../schemas/v1/release.schema.json)

---

## Bundle layout

`flightdeck release register` accepts either a single `release.yaml` file or a **bundle
directory** (any directory containing a `release.yaml`). The directory may include any
additional files referenced by `spec.prompts`, `spec.tools`, etc.

```
candidate-release/
├── release.yaml           # required
├── prompts/
│   ├── system.md          # referenced by spec.prompts.system_ref
│   └── user.md
└── tools.yaml             # referenced by spec.tools.manifest_ref
```

Files under `.git/` and `__pycache__/` are excluded from the checksum. Symlinks are also
skipped.

```bash
# Register a bundle directory
RELEASE_ID=$(flightdeck release register ./candidate-release)

# Register a single release.yaml
RELEASE_ID=$(flightdeck release register ./candidate-release/release.yaml)
```

The `--env` flag overrides `default_environment` from `flightdeck.yaml` for this
registration:

```bash
flightdeck release register ./candidate-release --env production
```

---

## Bundle checksum algorithm

The checksum is a SHA-256 hash over the **canonical bundle representation**, designed to be
stable across operating systems and line-ending conventions.

**Steps (`src/flightdeck/bundle.py`):**

1. Collect all files under the bundle path recursively. Exclude `.git/`, `__pycache__/`,
   and symlinks.
2. Sort files by their POSIX-style relative path (e.g. `prompts/system.md`).
3. For each file in sorted order:
   - **Text suffixes** (`.md`, `.yaml`, `.yml`, `.txt`, `.json`, `.csv`, `.toml`): read
     as UTF-8 and normalize CRLF (`\r\n`) and bare CR (`\r`) to LF (`\n`) before hashing.
   - **Binary suffixes**: hash raw bytes unchanged.
   - Feed the hasher: `relative/posix/path` + `\0` + `file_bytes` + `\0`.
4. The final digest is returned as a lowercase hex string (no `sha256:` prefix).

When `register` is called on a single file, only that file contributes to the hash (using
the file's parent directory as the base for the relative path).

**Why this matters:** if a release has already been promoted and you want to prove the
on-disk files have not changed since registration, run `release verify`. The same algorithm
runs and compares against the stored checksum.

```bash
flightdeck release verify rel_abc123 --path ./candidate-release
# OK: checksum matches for rel_abc123
#   sha256=e3b0c44298fc1c149afb...

# On mismatch: exits with code 2 (distinct from normal CLI error code 1)
```

---

## Workspace config (`flightdeck.yaml`)

`flightdeck init` writes `flightdeck.yaml` in the current directory. Almost all CLI commands
look for this file in the current working directory.

```yaml
api_version: v1
kind: WorkspaceConfig
db_path: .flightdeck/flightdeck.db   # SQLite database path
default_environment: local            # default environment for register/diff/promote
diff:
  min_candidate_runs: 500   # HIGH confidence threshold (candidate side)
  min_baseline_runs: 500    # HIGH confidence threshold (baseline side)
  min_low_runs: 50          # LOW confidence floor
# Optional: YAML PricingCatalog for cross-vendor comparable lines on diffs (see schemas/v1/pricing_catalog.schema.json)
# pricing_catalog_path: pricing/catalog.yaml
# Optional: when true, direct promote is rejected until a pending request is confirmed (HTTP/CLI request + confirm)
# promotion_requires_approval: false
```

All fields have defaults; an empty `flightdeck.yaml` is valid. `db_path` accepts any
relative or absolute path — the parent directory is created automatically on first use.

**`pricing_catalog_path`** — optional path to a [`PricingCatalog`](../schemas/v1/pricing_catalog.schema.json) YAML
(relative to the workspace cwd or absolute). When set, diffs include additive `pricing.catalog` / `pricing.hints`.
**`promotion_requires_approval`** — when `true`, `POST /v1/promote` and `flightdeck release promote` reject until a row is
completed via `POST /v1/promote/request` then `POST /v1/promote/confirm` (or CLI `release promote-request` / `promote-confirm`).
**`GET /v1/workspace`** exposes non-secret booleans for automation and the web UI (`promotion_requires_approval`,
`pricing_catalog_configured`, `server_version`).

`diff.*` thresholds are the **workspace defaults** used when the active policy does not
override them. The policy's `min_*` fields take precedence when set (including `0` for
"no minimum"). See [operations-and-policy.md § Confidence tiers](operations-and-policy.md).

---

## Pricing table YAML format

Pricing tables provide per-model token rates used by `compute_diff` to calculate
`cost_per_run_usd`. Each table is identified by `(provider, pricing_version)`.

```yaml
provider: openai           # required; matches spec.pricing_reference.provider
pricing_version: "2024-05" # required; matches spec.pricing_reference.pricing_version
entries:
  - model: gpt-4o
    input_usd_per_1k_tokens: 2.50
    output_usd_per_1k_tokens: 10.00
    cached_input_usd_per_1k_tokens: 1.25  # optional; omit if no cached rate
  - model: gpt-4o-mini
    input_usd_per_1k_tokens: 0.15
    output_usd_per_1k_tokens: 0.60
```

All rate fields are non-negative floats. `cached_input_usd_per_1k_tokens` defaults to
`null` when omitted; cached-token cost is only applied when the rate is set.

**JSON Schema:** [`schemas/v1/pricing_table.schema.json`](../schemas/v1/pricing_table.schema.json)

### Importing pricing tables

```bash
# First-time import
flightdeck pricing import pricing-openai-2024-05.yaml

# Replace an existing table (requires audit reason)
flightdeck pricing import pricing-openai-2024-05.yaml --replace --reason "corrected cached rate"

# Inspect an imported table
flightdeck pricing show --provider openai --version 2024-05
```

Every import — including `--replace` — writes a record to the `pricing_import_audit`
SQLite table. This record is retained even if the table is later replaced again.

| Column | Type | Description |
|--------|------|-------------|
| `import_id` | TEXT | `pim_` + 12 random hex chars |
| `provider` | TEXT | Matches the table's `provider` field |
| `pricing_version` | TEXT | Matches the table's `pricing_version` field |
| `action` | TEXT | `"insert"` (first import) or `"replace"` (with `--replace`) |
| `actor` | TEXT | Value of `$USER` / `$USERNAME` at import time |
| `reason` | TEXT | Rationale (required for `"replace"`, `null` for first imports) |
| `old_pricing_json` | TEXT | Serialized previous table contents; `null` for first imports |
| `new_pricing_json` | TEXT | Serialized new table contents |
| `new_checksum` | TEXT | SHA-256 hex of `new_pricing_json` (deterministic serialization) |
| `created_at` | TEXT | ISO-8601 timestamp of this audit event |

`--replace` requires `--reason` to be non-empty. Importing without `--replace` when a
table already exists returns an error.

To inspect the audit trail directly:

```bash
sqlite3 .flightdeck/flightdeck.db \
  "SELECT import_id, provider, pricing_version, action, actor, reason, created_at
   FROM pricing_import_audit ORDER BY created_at;"
```

### Pricing and diff accuracy

The diff compares each release using **its own `pricing_reference`** — a baseline and
candidate may reference different pricing versions. When they differ, the diff output flags
`pricing_or_model_changed: true` and prints a note warning that the cost delta includes
pricing assumption changes.

A diff fails with `OperationError` (HTTP 400 from the API) if either release's
`pricing_reference` does not match a loaded pricing table. Fix with
`flightdeck pricing import`.
