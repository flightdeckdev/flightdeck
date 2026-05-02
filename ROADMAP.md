# Roadmap

FlightDeck helps teams **ship AI agents safely** with release diffs, runtime evidence, and policy gates: immutable releases, trusted diffs, and policy-gated promotion.

This document is **strategy and ordering**, not a second changelog. It goes from **what is already shipped** to **what we are building next**, **why production can still feel standalone**, and **what stays off the table**. Per-version shipping notes live elsewhere (see below).

**Reality check:** FlightDeck is intentionally **local-first** (CLI + SQLite + optional `flightdeck serve`). That keeps trust boundaries explicit; teams still supply integration glue to run it broadly in production.

**Version detail:** The current shipping line is **v1.1.2**. For SemVer-by-SemVer behavior and migrations, use **[RELEASE_NOTES.md](RELEASE_NOTES.md)** and **[CHANGELOG.md](CHANGELOG.md)**.

---

## What is shipped (capability snapshot)

- **Release registry and verification:** versioned `release.yaml` artifacts with checksums, `flightdeck release verify`.
- **Economic + operational governance:** immutable pricing imports, trusted `release diff`, policy-gated `promote` and `rollback` (including optional approval request/confirm when configured).
- **Audit trail:** promotion/rollback history with stable sequencing (`audit_seq`) and integrity checks via `doctor`.
- **Evidence ingestion:** `runs ingest` from JSONL/JSON arrays plus stable `POST /v1/events` (`schemas/v1/`); **`GET /v1/runs`**, **`runs list`**, optional **`trace_id`** filter, and **`runs export`** (JSONL) for operator forensics.
- **Local API + UI:** `flightdeck serve` routes and shipped web bundle under `src/flightdeck/server/static/`; surfaces summarized in **Web UI and operator experience** below.
- **SDK and tooling:** Python sync/async clients with retries/batching and `flightdeck-quickstart-verify`.
- **Operator references:** CI examples, deploy/Compose guidance, Helm and fleet examples under `examples/`.

---

## Web UI and operator experience

Strategic UX intent for the bundled React app (routing and components: **[docs/web-ui.md](docs/web-ui.md)**). This is not a visual design spec; it keeps UI work aligned with evidence, diff trust, and promotion safety—not dashboard sprawl (see **[AGENTS.md](AGENTS.md)**).

**Principles**

- **Operator-first:** fewer steps to answer “Can I promote?” and “What broke?”; clarity over decoration.
- **Trust and safety:** mutations are obvious; token/read-only posture stays visible.
- **Evidence over chrome:** structured fields and light timelines where APIs are stable; raw JSON as an escape hatch, not the default reading path.
- **Density, not platforms:** guided flows and scannable summaries—no APM-style UI, no charting product.

**Shipped surfaces**

| Surface | Role |
|--------|------|
| **Overview** | Ledger / promotion snapshot, ledger metrics |
| **Diff** | Release comparison, pricing / catalog / hints, policy outcome |
| **Runs** | Forensics filters, listing, export |
| **Actions / Promote** | Direct promote vs approval request/confirm, rollback |
| **Shell** | Primary nav, security/status strip, optional read-only build |

**UX and UI backlog (grouped)**

These map to **What is next** items **1**, **2**, and **5**; ship notes stay in **RELEASE_NOTES** / **CHANGELOG**.

1. **Runs and forensics (web)** — Run or trace **detail** (drawer or page), clearer **empty and error** states, optional **timeline** grouping by `trace_id` / session, export affordances consistent with server limits.
2. **Diff comprehension** — Stronger **scannability** for policy blocks and pricing/catalog lines; surface **version skew** and hint copy when the API exposes it.
3. **Promotion and approval** — **Progressive disclosure** for approval vs direct promote, clearer confirmation copy, **pending requests** table polish.
4. **Overview and trust** — Metrics **context** (what a counter means), light cross-links to Diff/Runs—not a metrics dashboard product.
5. **Shell and quality bar** — **Loading** states, consistent spacing and type rhythm, keyboard **focus** and labels, layouts that tolerate narrow viewports where cheap.
6. **Security ergonomics (UI)** — Token/env/mutation visibility, read-only build behavior, cautious affordances for destructive actions.

**Explicit UI deferrals**

Out of scope for the near-term web app: theme marketplaces; embedded arbitrary log viewers; full observability or fleet consoles in the browser; multi-workspace UI (follows conditional **Fleet / cross-workspace** in **What is next**).

---

## Production readiness gaps (why it can feel standalone)

Gaps between “works locally” and “easy to use across production services.”

| Gap | What production-ready usually requires | FlightDeck intent |
|-----|----------------------------------------|-------------------|
| **Event pipeline** | Reliable `RunEvent` emission from app/agent runtimes. | Near term: reference integration examples; operator owns final runtime wiring. |
| **CI/GitOps flow** | Register → ingest → diff → gate → promote in pipelines. | Near term: maintained CI examples/templates. |
| **Deployment unit** | Repeatable `serve` packaging, health checks, process supervision. | Near term: container/compose guidance; still local-first by default. |
| **Identity and access** | Strong auth beyond loopback + optional bearer token. | Mid term: documented hardened patterns; first-class enterprise auth is a longer arc. |
| **Storage/availability** | Backup/restore, scaling, HA story. | Operator-owned today; improve docs and patterns. |
| **Observability integration** | Correlated telemetry export and operational visibility. | Mid term: OTLP-oriented integration paths (not an APM/dashboard product). |
| **Multi-workspace/fleet** | Cross-workspace views and policy coordination. | Long term and conditional; one workspace = one ledger today. |

---

## What is next (ordered)

Each item ties to the core promise: **release integrity**, **runtime evidence**, **policy-gated promotion**, and **auditability** (see **[AGENTS.md](AGENTS.md)**).

1. **Evidence and forensics (web)** — Replay/trace-oriented views and richer export semantics on top of `runs list`, `trace_id`, and JSONL export, so operators can reason over evidence without leaving the product surface. *UI details: **[Web UI and operator experience](#web-ui-and-operator-experience)**.*
2. **Catalog lifecycle and diff diagnostics** — Stronger mismatch signals beyond pricing-table row presence (for example version skew hints), strengthening economic governance on diffs. *UI details: **[Web UI and operator experience](#web-ui-and-operator-experience)**.*
3. **Integration glue** — Maintain app runtime emitters, CI/GitOps examples, and `serve` deployment recipes so the path from code to gated promotion is copy-pasteable.
4. **Serve and deployment hardening** — Clear operator narrative for health checks, supervision, and backup/restore alongside existing Compose/Helm references.
5. **Security ergonomics** — Continue explicit token/env status, mutation guardrails, and optional read-only UI patterns for local and bounded remote use. *UI details: **[Web UI and operator experience](#web-ui-and-operator-experience)**.*
6. **OTLP-oriented integration (mid term)** — Documented or thin adapter-style paths for correlated telemetry; not a commitment to an in-product APM.
7. **Fleet / cross-workspace (conditional)** — Broader governance surfaces only after the signals in **Horizons and conditions** below; default remains one workspace, one ledger.

Optional milestone framing (headline only): a **v1.2** line might emphasize **forensics + catalog diagnostics**; ship notes still land in **RELEASE_NOTES** / **CHANGELOG**.

---

## Horizons and conditions

### Near-term committed direction

The ordered list above is the default backlog shape: deepen evidence and diff trust, reduce integration friction, and harden how `serve` is run—not a pivot to a hosted control plane.

### Conditional directions (not committed by default)

- Optional hosted or federated control plane for cross-workspace policy and read models.
- Fleet-level analytics via export/read-model patterns (without turning the core into a general data warehouse).
- Deeper cost attribution and vendor/tool pricing coverage as the evidence model supports it.
- Provenance or supply-chain-style attestations only where they directly strengthen release trust boundaries.

### When to expand scope (e.g. fleet / platform options)

- Repeated external demand for cross-workspace governance.
- Clear operator pain that cannot be solved with local-first patterns plus documented integrations.
- Confidence that expansion does not break core trust boundaries and contract stability.

### Vision (directional only, not backlog)

- FlightDeck as a common release attestation reference for AI systems.
- Federated policy models across teams/workspaces with auditable inheritance.
- Ecosystem adapters that keep FlightDeck as a governance layer, not an agent framework.

---

## Success and readiness signals

Use **[examples/README.md](examples/README.md)** as a discoverability pass against these signals (not a product guarantee).

**Product (PMF wedge):**

- Teams treat release versioning + checksum verification as the source of truth for promotion decisions.
- Cost/latency/error diff output drives at least one real rollout decision (not demo-only usage).
- Policy gates actively block at least one unsafe promotion in normal team workflows.
- CI templates are adopted externally without local patching.

**Productization:**

- Approval-gated promotion is used in at least one end-to-end production pipeline.
- At least two provider pricing sources compare cleanly in one diff workflow.
- Teams can stand up and operate `flightdeck serve` with documented deployment guidance.

**Operator experience (web):**

- An operator can reach a **promote vs blocked-by-policy** conclusion from **Diff** and **Actions** without opening raw JSON first.
- A forensics task (for example trace-scoped triage) is completed from **Runs** without falling back to the CLI for the same filters and slice.

---

## Non-goals

Near-term exclusions match **[AGENTS.md](AGENTS.md)** (no prompt IDE, no agent framework, no gateway-by-default, no compliance-scanner product, no fine-tuning ops roadmap in core, no broad plugin system, no dashboard-heavy product before CLI/local HTTP is deeply proven). Hosted control plane and in-path traffic routing stay opt-in long-term considerations, not default posture.

---

## References

- **Contracts and trust:** [RELEASE_NOTES.md](RELEASE_NOTES.md), [CHANGELOG.md](CHANGELOG.md), [SECURITY.md](SECURITY.md)
- **Versioning:** [VERSIONING.md](VERSIONING.md)
- **Contributors/org workflow:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Engineering rules and doctrine:** [AGENTS.md](AGENTS.md)
- **Web UI routing and components:** [docs/web-ui.md](docs/web-ui.md)
