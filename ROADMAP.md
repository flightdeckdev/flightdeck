# Roadmap

FlightDeck is **AI release governance** for production agents: immutable releases, runtime evidence, trusted diffs, and policy-gated promotion.

This roadmap is meant to be clear from **what is already shipped** to **near-term commitments** and **long-horizon possibilities**. It also calls out what still makes the product feel standalone in production settings.

**Reality check:** today FlightDeck is intentionally **local-first** (CLI + SQLite + optional `flightdeck serve`). That keeps trust boundaries explicit, but it also means teams still need integration glue to run it broadly in production.

---

## What is shipped today

- **Release registry and verification:** versioned `release.yaml` artifacts with checksums, `flightdeck release verify`.
- **Economic + operational governance:** immutable pricing imports, trusted `release diff`, policy-gated `promote` and `rollback`.
- **Audit trail:** promotion/rollback history with stable sequencing (`audit_seq`) and integrity checks via `doctor`.
- **Evidence ingestion:** `runs ingest` from JSONL/JSON arrays plus stable `POST /v1/events` contracts (`schemas/v1/`).
- **Local API + UI:** `flightdeck serve` routes and web UI (Overview, Diff, Promote) in `src/flightdeck/server/static/`.
- **SDK and tooling:** Python sync/async clients with retries/batching and `flightdeck-quickstart-verify`.

---

## Next release

**v1.0.4 is shipped.** See **[CHANGELOG.md](CHANGELOG.md)** for the full list of additions. The
v1.0.4 slice delivered: `GET /v1/metrics` (JSON ledger counters), `pricing.prices` on
`POST /v1/diff`, CLI **Per-1k token prices** output, matching web diff banner detail, and the
**[examples/README.md](examples/README.md)** end-to-end walkthrough.

**v1.0.5 / next patch:** candidates include documentation completeness improvements (time-window
semantics, error message catalog, checksum format, tenant/task filter scope in UI), and
continued Phase 0 hardening. No breaking changes expected to stable CLI, HTTP, or
**`api_version` `v1`** contracts.

---

## Production readiness gaps (why it can feel standalone)

These are current gaps between "works locally" and "easy to use across production services."

| Gap | What production-ready usually requires | FlightDeck intent |
|-----|----------------------------------------|-------------------|
| **Event pipeline** | Reliable `RunEvent` emission from app/agent runtimes. | Near term: reference integration examples; operator owns final runtime wiring. |
| **CI/GitOps flow** | Register -> ingest -> diff -> gate -> promote in pipelines. | Near term: maintained CI examples/templates. |
| **Deployment unit** | Repeatable `serve` packaging, health checks, process supervision. | Near term: container/compose guidance; still local-first by default. |
| **Identity and access** | Strong auth beyond loopback + optional bearer token. | Mid term: documented hardened patterns; first-class enterprise auth is longer arc. |
| **Storage/availability** | Backup/restore, scaling, HA story. | Operator-owned today; improve docs and patterns. |
| **Observability integration** | Correlated telemetry export and operational visibility. | Mid term: OTLP-oriented integration paths (not an APM/dashboard product). |
| **Multi-workspace/fleet** | Cross-workspace views and policy coordination. | Long term and conditional; one workspace = one ledger today. |

---

## Phase 0: Foundation to PMF (near term, next releases)

Goal: prove the wedge with real teams using FlightDeck as release governance source-of-truth.

### Must ship in this phase

- Harden CLI/schema contracts and edge-case policy coverage (sample windows, sparse traffic, error paths).
- Add concrete integration references: app runtime event emitters, CI pipeline examples, and deployment recipes for `flightdeck serve`.
- Improve pricing normalization for multiple provider inputs while keeping diff semantics stable.
- Strengthen local security ergonomics: explicit token/env status in UI, mutation guardrails, optional read-only UX.
- Continue UI productization for current scope (structured views over raw JSON where stable).

### Phase 0 progress (v1.0.3–v1.0.4)

Shipped on **`main`**:

- **Policy / diff tests (v1.0.3):** `diff_releases` coverage for MEDIUM confidence vs `require_high_diff_confidence`, LOW sample floor boundaries, `max_latency_ms` (including skip when latency is absent), `max_error_rate`, and stacked policy failure reasons; CLI integration for MEDIUM blocking a second promotion after a baseline is established.
- **Ingest tests (v1.0.3):** empty JSONL (zero inserts), malformed line (non-zero exit), JSON array file accepted.
- **Multi-provider pricing (v1.0.3):** integration tests that diff baseline vs candidate releases with different **`pricing_reference`** providers (and same-provider different models), including parity checks on **`POST /v1/diff`** `pricing.pricing_or_model_changed`.
- **Web UI (v1.0.3):** structured outcome card after promote/rollback (policy, pointer, IDs) with raw JSON in a collapsible panel; Diff summary shows pricing/model change when the server marks it.
- **Pricing diagnostics (v1.0.4):** **`pricing.prices`** on **`POST /v1/diff`** and matching CLI / web lines for per-1k input/output unit prices when pricing or model differs.
- **Operating narrative (v1.0.4):** **[examples/README.md](examples/README.md)** index tying emit → ingest → verify → diff/gate → promote → serve.
- **Observability foundation (v1.0.4):** **`GET /v1/metrics`** JSON counters over the local ledger (not Prometheus/OTel; longer arc stays mid term).

**Still open in Phase 0** (see gaps table and Phase 1): **catalog-level** multi-provider normalization (single comparable unit across vendors), deeper **event pipeline** and **fleet** ergonomics, and **OTLP-oriented** telemetry remain beyond this patch.

### Phase-0 success signals

- Teams use release versioning + checksum verification as the source of truth for promotion decisions.
- Cost/latency/error diff output drives at least one real rollout decision (not demo-only usage).
- Policy gates actively block at least one unsafe promotion in normal team workflows.
- CI templates are adopted externally without local patching.

---

## Phase 1: Productization (mid term, roughly quarters)

Goal: move from solid local tooling to repeatable production usage patterns.

### Build in this phase

- Human-in-the-loop approval workflow on top of policy gates (without requiring a hosted control plane).
- Stronger multi-provider pricing normalization and clearer mismatch diagnostics.
- Incident forensics improvements (replay/trace-style analysis over ingested evidence) as governance support tooling.
- Deployment hardening artifacts (for example Helm or equivalent) if a blessed server topology is chosen.
- Multi-workspace operator ergonomics (naming, templates, reproducible setup patterns).

### Phase-1 readiness signals

- Approval-gated promotion is used in at least one end-to-end production pipeline.
- At least two provider pricing sources compare cleanly in one diff workflow.
- Teams can stand up and operate `flightdeck serve` with documented deployment guidance.

---

## Phase 2: Scale and platform options (long term, conditional)

Goal: expand from single-workspace governance to broader fleet patterns when demand is proven.

### Candidate directions (conditional, not committed by default)

- Optional hosted/federated control plane for cross-workspace policy and read models.
- Fleet-level analytics via export/read-model patterns (without turning core into a general data warehouse).
- Deeper cost attribution and vendor/tool pricing coverage once evidence model supports it.
- Provenance/supply-chain style attestations if they directly strengthen release trust boundaries.

### Conditions to enter Phase 2

- Repeated external demand for cross-workspace governance.
- Clear operator pain that cannot be solved with local-first patterns + documented integrations.
- Confidence that expansion does not break core trust boundaries and contract stability.

---

## Phase 3: Super long term (vision only, highly conditional)

- FlightDeck as a common release attestation standard for AI systems.
- Federated policy models across teams/workspaces with auditable inheritance.
- Broader ecosystem adapters that preserve FlightDeck's role as governance layer, not agent framework.

These are directional, not committed backlog items.

---

## Explicit non-goals (near term, aligned with AGENTS.md)

- No prompt IDE, no agent framework, no gateway/proxy-by-default.
- No compliance-scanner product as a near-term deliverable.
- No fine-tuning operations roadmap in core.
- No broad plugin/marketplace direction near term.
- No dashboard-heavy product before CLI/local HTTP reliability is deeply proven.

Hosted control plane and in-path traffic routing remain opt-in long-term considerations, not default product posture.

---

## References

- **Contracts and trust:** `RELEASE_NOTES.md`, `CHANGELOG.md`, `SECURITY.md`
- **Versioning:** `VERSIONING.md`
- **Contributors/org workflow:** `CONTRIBUTING.md`
- **Engineering rules and doctrine:** `AGENTS.md`
