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

## Next Steps (Execution Plan)

### Target next release: v1.1.0 (UI-assisted local operations)

- Deliver a minimal local UI that complements the CLI, not replaces it.
- Keep local-first trust boundaries: no hosted control plane dependency and no default remote services.
- Ship UI only for workflows already stable in CLI to avoid contract drift.

### Phase 1: Stabilize v1 operations (next 2-4 weeks)

- Finalize CLI contract coverage around `release diff`, `release promote`, `release rollback`, and `doctor`.
- Expand schema fixture coverage in `tests/fixtures/json/` for edge-case payloads and error paths.
- Tighten release audit tests for promotion and rollback history ordering (`audit_seq` continuity).
- Keep local-first reliability high on Windows by maintaining temp-dir and SQLite lock regression tests.

### Phase 2: UI MVP + developer ergonomics (next 1-2 months)

UI MVP scope (ship fast):

- Read-only release timeline view (registered releases, promoted pointer, recent actions).
- Diff runner form (`baseline`, `candidate`, `window`, filters) with confidence and policy output.
- Promotion history panel with reasons and PASS/FAIL status.
- Safe action guardrails in UI: require reason text for promote/rollback and show confirmation prompts.

Implementation constraints for UI MVP:

- UI reads/writes through existing local HTTP/CLI contracts only.
- Reuse existing validation and policy paths; no separate business logic stack in UI.
- Include parity tests for one end-to-end path (CLI vs UI-triggered operation producing the same outcome).

- **Shipped (slim repo):** Python SDK retries, batching, **`AsyncFlightdeckClient`**, HTTP read/mutate helpers + optional **`api_token`**; **`flightdeck-quickstart-verify`**; Playwright smoke under **`web/e2e/`** (see **`web/README.md`**).
- Refine actionable CLI errors for pricing/model mismatches and unsupported policy states.

### Phase 3: Hardening and scale signals (next 1-2 quarters)

- Formalize schema compatibility guidance for additive vs breaking payload evolution.
- Add larger-window ledger test scenarios to validate confidence labels under sparse and bursty traffic.
- Expand policy evaluation coverage for mixed rollout conditions (cost, latency, and error-rate interactions).
- Continue publishing-only hardening (tag/version checks, schema drift checks, reproducible builds).

## References

- Contract and release posture: **[RELEASE_NOTES.md](RELEASE_NOTES.md)**
- Versioning policy: **[VERSIONING.md](VERSIONING.md)**
- Contributor and org-push guidance: **[CONTRIBUTING.md](CONTRIBUTING.md)**
- Canonical repository: **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)**

## Later

- Hosted control plane
- Dashboard
- OpenTelemetry import/export mapping
- Tool-cost pricing
- Enterprise controls
