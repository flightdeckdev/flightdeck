# FlightDeck web UI (React + Vite)

Source for the local UI served by **`flightdeck serve`** at **`/`**. Production bundles are emitted to **`../src/flightdeck/server/static/`** (FastAPI serves **`index.html`** and hashed files under **`/assets/`**).

## Commands

```bash
cd web
npm ci
npm run build
cd ..
git diff --exit-code src/flightdeck/server/static/
```

After any change under **`web/src/`** (or **`vite.config.ts`**, **`package.json`**, lockfile, etc.) that affects the production bundle, run **`npm run build`** again, ensure the **`git diff --exit-code`** above is clean from the repo root, and commit the updated **`src/flightdeck/server/static/`** tree. The build runs **`scripts/normalize-static-lf.mjs`** after Vite so emitted HTML/JS/CSS use **LF** on Windows (avoids CRLF-only noise against **`.gitattributes`**). **CI** rebuilds and runs the same **`git diff --exit-code`** on that path so committed assets cannot drift.

## Local development (`npm run dev`)

1. In one terminal, run the API from a workspace with **`flightdeck.yaml`** (default **`8765`**):

   ```bash
   flightdeck serve
   ```

2. In another:

   ```bash
   cd web
   cp .env.example .env.local   # optional: set VITE_FLIGHTDECK_LOCAL_API_TOKEN
   npm ci
   npm run dev
   ```

**Vite** proxies **`/v1/*`** and **`/health`** to **`http://127.0.0.1:8765`** (override with **`VITE_DEV_PROXY_TARGET`** in **`.env.local`** or the environment). The React app calls relative **`/v1/...`** URLs so the browser talks to the Vite dev server only.

**Auth:** when the server has **`FLIGHTDECK_LOCAL_API_TOKEN`** set, set **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** in **`.env.local`** to the same value so promote/rollback requests include **`Authorization: Bearer ...`**.

## Playwright E2E

**CI** (Ubuntu + Windows) and the **PyPI release** workflow run **`npm run test:e2e`** after the production **`static/`** build. One-time browser download locally:

```bash
cd web
npm ci
npx playwright install chromium
npm run test:e2e
```

**`playwright.config.ts`** starts **`scripts/e2e-server.mjs`**: a fresh workspace under **`.tmp/playwright-fd-workspace/`**, then **`flightdeck serve`** on **`http://127.0.0.1:9876`**. On GitHub Actions the server uses **`uv run flightdeck ...`**; locally it uses **`python -m flightdeck.cli.main`** or **`py -3`**.

Run **`npm`** commands from this **`web/`** directory (repo root is one level up: **`cd web`**).

## App structure

The UI is a React 19 + TypeScript single-page application using **`HashRouter`** from `react-router-dom`. All navigation uses hash-based URLs so the FastAPI static file handler only needs to serve `index.html` for every route.

### Routing

| URL hash | Component | Nav label |
|----------|-----------|-----------|
| `/#/` (default) | `OverviewPage` | Overview |
| `/#/diff` | `DiffPage` | Diff |
| `/#/actions` | `ActionsPage` | Promote |

Any unrecognized hash redirects to `/#/`. **`AppShell`** (`web/src/components/AppShell.tsx`) renders the persistent header and `<nav>` links, wraps children in `TimelineRefreshProvider`, and provides the `<Outlet>` for nested routes.

### Pages

**`OverviewPage`** (`web/src/pages/OverviewPage.tsx`)
Read-only dashboard. On mount (and on every `generation` tick from `TimelineRefreshContext`) it calls `loadTimeline()` -- a parallel fetch of `/v1/releases`, `/v1/promoted`, and `/v1/actions` -- and renders three tables: Releases, Promoted, and Recent actions. A "Refresh" button triggers a manual reload. Errors surface as an inline alert; IDs are truncated to `first10...last6` with the full value in the `title` attribute.

**`DiffPage`** (`web/src/pages/DiffPage.tsx`)
Form-driven diff computation. Submits `POST /v1/diff` with `baseline_release_id`, `candidate_release_id`, `window`, and `environment`. On success renders a metrics summary (cost per run, latency avg, error rate with delta vs baseline), a policy PASS/FAIL badge, sample counts, and a collapsible raw-JSON panel.

**`ActionsPage`** (`web/src/pages/ActionsPage.tsx`)
Promote and rollback form (nav label: **"Promote"**, page title: **"Promote & rollback"**, route: `/#/actions`). Submits `POST /v1/promote` or `POST /v1/rollback` with `release_id`, `environment`, `window`, `reason`, and `actor: "react-ui"`. Requires a non-empty reason; shows a browser confirmation dialog before sending. On success calls `notifyTimelineMutated()` so the Overview table refreshes. Buttons disable during in-flight requests.

### API helpers (`web/src/api.ts`)

- **`fetchJson<T>(path, init?)`** -- wrapper around `fetch` that injects `Authorization: Bearer <token>` when `VITE_FLIGHTDECK_LOCAL_API_TOKEN` is set, and throws a descriptive `Error` for non-2xx responses.
- **`loadTimeline()`** -- parallel-fetches `/v1/releases`, `/v1/promoted`, and `/v1/actions` and returns a combined `TimelinePayload`.
- Types: `ReleaseRow`, `PromotedRow`, `ActionRow`, `TimelinePayload`.

### Timeline refresh context (`web/src/context/TimelineRefreshContext.tsx`)

`TimelineRefreshProvider` holds a `generation` integer. Any component that mutates server state calls `notifyTimelineMutated()` to increment `generation`. `OverviewPage` includes `generation` as a `useEffect` dependency, so it automatically re-fetches when a mutation completes -- without a full page reload.

Flow:
1. Mutation succeeds in `ActionsPage` -- calls `notifyTimelineMutated()`
2. `generation` increments in `TimelineRefreshContext`
3. `OverviewPage`'s `useEffect([generation, refresh])` fires -- calls `loadTimeline()` -- tables update
