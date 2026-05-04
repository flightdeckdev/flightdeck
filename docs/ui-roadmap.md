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

## Production wireframe direction (external — change → impact → policy → decision)

This section folds **final wireframe** feedback into the same constraints as **Blueprint alignment**: useful as **layout and component targets**, not as a promise that every block exists on the wire today.

### Thesis (keep)

The UI should reinforce **change → impact → policy → decision**, not generic dashboards. Prefer **deepening diff causality and decision clarity** over charts and vanity metrics (already in **Non-goals**).

### Target section stack (conceptual)

| Section | Role | FlightDeck today (serve UI) | Next evolution |
|--------|------|----------------------------|----------------|
| Sidebar | Stable nav | `AppShell` | Optional rename **Runs → Evidence** if it helps operators without splitting routes. |
| Release header | Human anchor for the release under review | Overview `?release=` hero; Diff form IDs | Dedicated **`/release/:id`** or shared **`ReleaseHeader`** component fed by timeline + focused release. |
| Block reason banner | Unmissable “why stop” | Diff verdict banner (policy FAIL + reasons) | Optional **single-line primary reason** when server ranks or summarizes reasons. |
| Release twin (OLD vs NEW) | At-a-glance identity change | Pricing model line + rollups (Diff) | Explicit **baseline vs candidate** strip (version/agent/env + model/provider) once data is stable in **`POST /v1/diff`**. |
| Change impact analysis (expandable) | Causal / drill-down | Collapsible pricing/catalog + metric grid | **Structured change list** only when diff payload exposes comparable artifacts (prompt/tools deltas)—no invented causality. |
| Policy evaluation | Gate outcome | Verdict banner + policy reasons | Optional **`PolicyPanel`** extracting banner + evaluated_at for reuse on Actions outcomes. |
| Approvals | Human layer | **Actions** when `promotion_requires_approval` | Not multi-role org charts until backend supports it; keep **request / confirm** truthy UI. |
| Decision | Readable outcome | PASS/FAIL copy + promote CTA | **`DecisionCard`** summarizing verdict + next step (promote / fix / widen evidence). |
| Actions | Mutations | Promote / rollback / request / confirm | Same page; ensure cross-links from Diff retain window/env. |

### Suggested components (map to repo gradually)

Names from feedback are **targets** for extraction/refactor—not required file renames in one PR:

- **`ReleaseHeader`** — consolidate Overview hero + future release route header.
- **`ReleaseTwin`** — thin summary row for baseline vs candidate (model/pricing/version IDs).
- **`DiffList` / change rows** — defer until **`changes[]`** (or equivalent) exists on the API.
- **`PolicyPanel`** — wrapper around policy PASS/FAIL + reasons + timestamp.
- **`ApprovalPanel`** — pending requests + confirm flow (today on Actions).
- **`DecisionCard`** — verdict + recommended action line.

### Illustrative data shape (not current wire contract)

A unified front-end model such as:

```ts
// Illustrative only — do not treat as implemented HTTP schema.
type Release = {
  id: string;
  status: "blocked" | "ready";
  changes: Change[];
  policies: PolicyResult[];
  approvals: Approval[];
};
```

…only makes sense after the server can compute **`blocked` vs `ready`** for a **specific evaluation context** (baseline, window, environment) and optionally expose **`changes[]`**. Until then, compose views from **`TimelinePayload`**, **`POST /v1/diff`**, **`GET /v1/runs`**, and promotion APIs **without** implying a single merged **`Release`** document.

### Hard “don’t” (reasserted)

- Do **not** add chart-heavy dashboards or random metric walls.
- Do **not** fake approval chains or policy catalogs without API backing.

### Relation to open UI work (e.g. PR #53 trajectory)

Recent UI slices already move toward this wireframe: **verdict-first Diff**, **collapsed deep pricing**, **promoted-first Overview**, **copy/filters**, **decision-litmus copy**. Remaining gap is mostly **component extraction** and **release route / twin row**, gated on contracts above.
