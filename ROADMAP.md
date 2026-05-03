# Roadmap

FlightDeck helps teams **ship AI agents safely** with release diffs, runtime evidence, and policy gates: immutable releases, trusted diffs, and policy-gated promotion.

This document is **strategy and ordering**, not a second changelog. It goes from **what is already shipped** to **what we are building next**, **why production can still feel standalone**, and **what stays off the table**. Per-version shipping notes live elsewhere (see below).

**Reality check:** FlightDeck is intentionally **local-first** (CLI + SQLite + optional `flightdeck serve`). That keeps trust boundaries explicit; teams still supply integration glue to run it broadly in production.

**Version detail:** The current shipping line is **v1.2.0**. For SemVer-by-SemVer behavior and migrations, use **[RELEASE_NOTES.md](RELEASE_NOTES.md)** and **[CHANGELOG.md](CHANGELOG.md)**.

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

| Surface | Role | Operator outcome (intent) |
|--------|------|----------------------------|
| **Overview** | Ledger / promotion snapshot, ledger metrics | See promotion posture and ledger health at a glance before opening Diff or Runs. |
| **Diff** | Release comparison, pricing / catalog / hints, policy outcome | Decide promote vs blocked with scannable economics and policy, not raw JSON first. |
| **Runs** | Forensics filters, listing, export | Narrow to the slice that explains a spike or incident without re-ingesting elsewhere. |
| **Actions / Promote** | Direct promote vs approval request/confirm, rollback | Complete an auditable promotion or rollback with clear guardrails. |
| **Shell** | Primary nav, security/status strip, optional read-only build | Trust posture (token, read-only) stays visible while navigating. |

**UX and UI backlog (grouped)**

These map to **What is next** items **1**, **2**, and **5**; ship notes stay in **RELEASE_NOTES** / **CHANGELOG**.

1. **Outcome:** an engineer can open a **single run or trace** view and answer “what happened on this request?” without leaving the app — **Runs and forensics (web):** run or trace **detail** (drawer or page), clearer **empty and error** states, optional **timeline** grouping by `trace_id` / session, export affordances consistent with server limits.
2. **Outcome:** a reviewer spots **policy blocks** and **pricing skew** in seconds — **Diff comprehension:** stronger **scannability** for policy blocks and pricing/catalog lines; surface **version skew** and hint copy when the API exposes it.
3. **Outcome:** an approver completes **request → confirm** without ambiguity — **Promotion and approval:** **progressive disclosure** for approval vs direct promote, clearer confirmation copy, **pending requests** table polish.
4. **Outcome:** counters on Overview are **interpretable**, not decorative — **Overview and trust:** metrics **context** (what a counter means), light cross-links to Diff/Runs—not a metrics dashboard product.
5. **Outcome:** the UI feels **fast and accessible** on a laptop — **Shell and quality bar:** **loading** states, consistent spacing and type rhythm, keyboard **focus** and labels, layouts that tolerate narrow viewports where cheap.
6. **Outcome:** operators **see** when mutations or tokens apply — **Security ergonomics (UI):** token/env/mutation visibility, read-only build behavior, cautious affordances for destructive actions.
7. **Outcome:** dense operator layouts stay **readable** without a bespoke design system — **Visual system:** shared typography scale, spacing rhythm, **focus-visible** affordances, and narrow-layout breakpoints so the operator surfaces stay legible without a separate design system product.

**Explicit UI deferrals**

Out of scope for the near-term web app: custom themes or theme marketplaces; embedded arbitrary log viewers; full observability or fleet consoles in the browser; multi-workspace UI (follows conditional **Fleet / cross-workspace** in **What is next**).

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

1. **Outcome:** operators **pinpoint the run or trace** behind a regression or cost jump from the web — **Evidence and forensics (web):** replay/trace-oriented views and richer export semantics on top of `runs list`, `trace_id`, and JSONL export, so operators can reason over evidence without leaving the product surface. *UI details: **[Web UI and operator experience](#web-ui-and-operator-experience)**.*
2. **Outcome:** economic diffs **surface version and naming skew** before a bad promote — **Catalog lifecycle and diff diagnostics:** stronger mismatch signals beyond pricing-table row presence (for example version skew hints), strengthening economic governance on diffs. *UI details: **[Web UI and operator experience](#web-ui-and-operator-experience)**.*
3. **Outcome:** a new service reaches **register → ingest → diff → gate** using **maintained examples** — **Integration glue:** maintain app runtime emitters, CI/GitOps examples, and `serve` deployment recipes so the path from code to gated promotion is copy-pasteable.
4. **Outcome:** **`flightdeck serve`** in production is **boring to operate** (health, restarts, backups) — **Serve and deployment hardening:** clear operator narrative for health checks, supervision, and backup/restore alongside existing Compose/Helm references.
5. **Outcome:** teams using **Bearer** and read-only builds **do not foot-gun** — **Security ergonomics:** continue explicit token/env status, mutation guardrails, and optional read-only UI patterns for local and bounded remote use. *UI details: **[Web UI and operator experience](#web-ui-and-operator-experience)**.*
6. **Outcome:** correlated **infra** telemetry can sit **next to** ledger evidence without becoming an APM product — **OTLP-oriented integration (mid term):** documented or thin adapter-style paths for correlated telemetry; not a commitment to an in-product APM.
7. **Outcome (conditional):** multi-team governance **without** breaking one-ledger trust — **Fleet / cross-workspace (conditional):** broader governance surfaces only after the signals in **Horizons and conditions** below; default remains one workspace, one ledger.

**v1.2.0** ships the Python **3.11+** floor, **HTTP access** tightening for ingest and read APIs when a local token is set, **bundled default pricing** on **`flightdeck init`**, optional **PostgreSQL**, **runs export** / filters, substantial **web** operator UX, and experimental **`flightdeck.integrations`**. Deeper **catalog diagnostics** and **forensics** workstreams continue under **What is next**; ship notes live in **RELEASE_NOTES** / **CHANGELOG**.

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

- **Outcome:** within one **Diff** + **Actions** pass, an operator states **promote vs blocked-by-policy** without opening raw JSON first.
- **Outcome:** within about **two minutes**, an engineer **isolates the run or trace** responsible for a cost or error spike using **Runs** filters and export—without re-running the CLI for the same slice.

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
