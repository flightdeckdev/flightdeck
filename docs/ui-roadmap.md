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

| Priority | Work |
|----------|------|
| P1 | Collapse or relocate **Ledger metrics** on Overview so the releases + promoted story leads. |
| P1 | **Reorder Diff result**: top fold = verdict + key deltas; pricing/catalog in collapsed sections or tabs. |
| P1 | **Promoted vs candidate** narrative per `agent + environment` (e.g. inline summary above tables). |
| P1 | Reduce reliance on **manual checksum scanning** — surface version + agent + env as the human keys. |

## Phase 2 — Polish and operator UX

| Priority | Work |
|----------|------|
| P2 | Typography scale for page vs card titles; consistent vertical rhythm. |
| P2 | Table ergonomics: row hover, optional filters, copy-to-clipboard for release IDs. |
| P2 | Tone down gradient accents for a more **infra / audit** aesthetic (keep accessible contrast). |
| P2 | Copy pass: each primary page answers *What changed?* *Is it safe?* *Can I ship?* in one short block. |

## Non-goals (near term)

- Embedded orchestration or graph execution.
- Chart-heavy analytics dashboards (prefer summary metrics tied to gates).
- Replacing the CLI registration / ingest workflow.

## Verification

After `web/` changes: from `web/`, `npm ci && npm run build`; commit `src/flightdeck/server/static/` updates; run `npm run test:e2e` when navigation or forms behavior changes.

On Unix hosts where `python` is not on `PATH`, set `FLIGHTDECK_E2E_PYTHON` to a Python that has FlightDeck installed (for example the repo venv: `FLIGHTDECK_E2E_PYTHON=/path/to/.venv/bin/python npm run test:e2e`). The default is `python3`.
