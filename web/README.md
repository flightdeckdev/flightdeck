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

**Auth:** when the server has **`FLIGHTDECK_LOCAL_API_TOKEN`** set, set **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** in **`.env.local`** to the same value so promote/rollback requests include **`Authorization: Bearer …`**.

## Playwright E2E

**CI** (Ubuntu + Windows) and the **PyPI release** workflow run **`npm run test:e2e`** after the production **`static/`** build. One-time browser download locally:

```bash
cd web
npm ci
npx playwright install chromium
npm run test:e2e
```

**`playwright.config.ts`** starts **`scripts/e2e-server.mjs`**: a fresh workspace under **`.tmp/playwright-fd-workspace/`**, then **`flightdeck serve`** on **`http://127.0.0.1:9876`**. On GitHub Actions the server uses **`uv run flightdeck …`**; locally it uses **`python -m flightdeck.cli.main`** or **`py -3`**.

Run **`npm`** commands from this **`web/`** directory (repo root is one level up: **`cd web`**).

## Architecture

The source is organized under **`web/src/`**:

| Path | Purpose |
|------|---------|
| `main.tsx` | React entry point; mounts `<App />` into `#root` |
| `App.tsx` | `HashRouter` with routes for `OverviewPage`, `DiffPage`, and `ActionsPage` inside `AppShell` |
| `api.ts` | Typed fetch helpers (`fetchJson`, `loadTimeline`) and row types (`ReleaseRow`, `ActionRow`, …) |
| `components/AppShell.tsx` | Persistent header with primary nav links; wraps `TimelineRefreshProvider` |
| `components/Badge.tsx` | Inline `PASS`/`FAIL` badge with tone variants |
| `components/JsonPanel.tsx` | Collapsible raw JSON panel used on Diff and Actions pages |
| `context/TimelineRefreshContext.tsx` | Shared `generation` counter; incremented after successful mutations so `OverviewPage` re-fetches automatically |
| `pages/OverviewPage.tsx` | Releases, promoted pointers, and recent actions tables |
| `pages/DiffPage.tsx` | Interactive diff form; renders metric cards and policy result |
| `pages/ActionsPage.tsx` | Promote and rollback form; calls `notifyTimelineMutated()` on success |
| `index.css` | All scoped `fd-*` CSS classes (no external CSS framework) |

For user-facing UI documentation (what each page does, authentication, common issues) see **[docs/web-ui.md](../docs/web-ui.md)**.
