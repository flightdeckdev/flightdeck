# FlightDeck Serve UI roadmap

This document turns the strict UI review into sequenced work. Scope is the checked-in React app under `web/` (served from `flightdeck serve`). Goal: move from **ledger viewer** to a **release-centric control plane** without changing core product boundaries (CLI-first, local ledger).

## Principles

1. **One spine**: a release under judgment → diff verdict → promotion action (evidence on demand).
2. **URL is state**: deep links prefill forms so operators can share “this comparison” and “this promotion.”
3. **Verdict before detail**: policy outcome and blockers must dominate; tables and JSON stay secondary.
4. **Boring over flashy**: prefer clear hierarchy and high-contrast failure states over decorative chrome.

## Phase 0 — Done in repo (this slice)

| Item | Outcome |
|------|---------|
| Release-centric hero | Overview highlights a focused release when `?release=` is set; row shortcuts jump to Diff / Runs / Promote with params. |
| Wire navigation to state | `Diff`, `Runs`, and `Promote` read `baseline`, `candidate`, `release_id`, `window`, `environment` from the URL search string. |
| Blocked / pass unavoidable | Diff page shows a full-width **verdict banner** (alert on FAIL) above the result card stack. |
| Bridge Diff → Promote | After a computed diff, a primary **Continue to promote** action links to Promote with release + environment + window prefilled (read-only builds omit). |

## Phase 1 — Hierarchy and differentiation

| Priority | Work | Status |
|----------|------|--------|
| P1 | Collapse or relocate **Ledger metrics** on Overview so the releases + promoted story leads. | Done — metrics in collapsible panel below tables (collapsed by default). |
| P1 | **Reorder Diff result**: top fold = verdict + key deltas; pricing/catalog in collapsed sections or tabs. | Done — verdict banner; samples + rollups; pricing summary inline with expandable detail. |
| P1 | **Promoted vs candidate** narrative per `agent + environment` (e.g. inline summary above tables). | Done — promoted table first with version column; releases show Live vs Registered. |
| P1 | Reduce reliance on **manual checksum scanning** — surface version + agent + env as the human keys. | Done — Primary column on releases table; hero leads with agent/version/env. |

## Phase 2 — Polish and operator UX

| Priority | Work | Status |
|----------|------|--------|
| P2 | Typography scale for page vs card titles; consistent vertical rhythm. | Done — `fd-page-sub--tight` / `--meta`, wider page header measure. |
| P2 | Table ergonomics: row hover, optional filters, copy-to-clipboard for release IDs. | Done — filter row on releases; copy buttons; hover accent on `fd-table--hover`. |
| P2 | Tone down gradient accents for a more **infra / audit** aesthetic (keep accessible contrast). | Done — solid primary buttons; flat logo tile; nav indicator unchanged. |
| P2 | Copy pass: each primary page answers *What changed?* *Is it safe?* *Can I ship?* in one short block. | Done — Overview, Diff, Runs, Actions, Settings intros. |

## Non-goals (near term)

- Embedded orchestration or graph execution.
- Chart-heavy analytics dashboards (prefer summary metrics tied to gates).
- Replacing the CLI registration / ingest workflow.

## Verification

After `web/` changes: from `web/`, `npm ci && npm run build`; commit `src/flightdeck/server/static/` updates; run `npm run test:e2e` when navigation or forms behavior changes.

On Unix hosts where `python` is not on `PATH`, set `FLIGHTDECK_E2E_PYTHON` to a Python that has FlightDeck installed (for example the repo venv: `FLIGHTDECK_E2E_PYTHON=/path/to/.venv/bin/python npm run test:e2e`). The default is `python3`.

## Blueprint alignment (external product IA review)

This section maps a fuller “control plane” blueprint to FlightDeck’s **current** CLI-first ledger and HTTP surface. Use it to avoid building UI that implies APIs or workflows we do not ship yet.

### Adopted from the blueprint

- **Page litmus**: each primary screen should answer at least one of — *What changed?* · *What happened because of it?* · *Can I ship?*
- **Cross-page consistency**: shared status semantics (pass / fail / warn / neutral), fixed vocabulary (**Release**, **Diff**, **Policy**, **Evidence**), repeated rhythm (**header → summary → detail → actions**).
- **Sparse chrome**: summary metrics and tables over chart-heavy dashboards (matches roadmap non-goals).
- **Diff as differentiator**: structured comparison and policy outcome stay central; layout can evolve toward “baseline vs candidate” twin + verdict-first fold (Phase 1).
- **Evidence as ground truth**: runs + rollups remain the forensic surface; avoid Langfuse-style analytics_scope creep.
- **Component direction**: prefer one reusable set (`ReleaseHeader`, `StatusBadge`, `MetricCard`, etc.) over one-off page styling.

### Merged information architecture (near term)

Avoid exploding to eight top-level nav items before contracts exist. Practical sequencing:

1. **Overview** — situational awareness; add promoted / last-action strip before burying operators in ledger counters (Phase 1).
2. **Releases** — table-first browsing (today: Overview table; later: dedicated route if needed).
3. **Release detail** — evolve `?release=` hero into `/release/:id` when we want a stable bookmark per artifact.
4. **Diff** — deep dive; expand “change → impact → policy” **only** when diff payloads expose comparable structure (prompt/tools/model deltas as data, not copy).
5. **Evidence** — Runs page (rename in nav only if it helps operators).
6. **Promote** — Actions; surface approval flow when `promotion_requires_approval` is on (today: request / confirm API).

Defer standalone **Policies** (rule catalog with thresholds), **multi-role approval chains**, and **rich audit timeline filters** until read APIs and persistence match those stories.

### Deferred / backend-gated (do not imply in UI yet)

- **Per-release row status** (“Blocked”, “Live”, “Rolled back”) with sortable **cost Δ / latency Δ**: “Live” can align with promoted pointers; “blocked” is **evaluation-scoped** (depends on baseline, window, environment)—not a global attribute unless we store or cache last evaluation per release.
- **Policies page** listing rules with “expected vs actual”: needs a stable **rule listing** or workspace-backed contract; today policy output is **evaluated reasons**, not necessarily a browsable catalog.
- **Approvals** as org chart (Platform → ML → Security): requires identity, roles, and workflow beyond optional promotion request/confirm.
- **Risk score** / composite **HIGH** labels: needs a defined server-side aggregate or explicit mapping from existing fields (e.g. sample confidence alone is not a full risk model).
- **Release twin** lines such as “system prompt +N tokens” unless those deltas exist on the wire from release/diff payloads.

### Terminology note

Treat **policy FAIL** as **do not promote this candidate under this evaluation context** (baseline + window + environment), not “this release ID is permanently blocked everywhere.”
