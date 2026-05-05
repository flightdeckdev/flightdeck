# FlightDeck web UI (React + Vite)

Source for the local UI served by **`flightdeck serve`** at **`/`**. Production bundles are emitted to **`../src/flightdeck/server/static/`** (FastAPI serves **`index.html`** and hashed files under **`/assets/`**).

**App mark:** keep **`web/public/flightdeck-icon.png`** in sync with **`web/src/assets/flightdeck-icon.png`** (same bytes). The bundled copy is what the React shell and favicon use in production; the public copy is copied to **`static/flightdeck-icon.png`** for the stable **`/flightdeck-icon.png`** URL.

**Theming and brand:** the README overview image is **desired-state art**, not a UI spec. Incremental plan (tokens, optional dark mode, cyan–purple accents) lives under **[Theming and brand alignment](../docs/web-ui.md#theming-and-brand-alignment)** in **`docs/web-ui.md`**.

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

**Auth:** when the server has **`FLIGHTDECK_LOCAL_API_TOKEN`** set, set **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** in **`.env.local`** to the same value so **`GET /v1/*`** and promote/rollback requests include **`Authorization: Bearer …`**.

**Read-only UI:** set **`VITE_FLIGHTDECK_UI_READ_ONLY=true`** to hide the Promote nav entry and block **`#/actions`** (demos / wall displays). The shell still loads **`/health`** and shows a read-only banner.

## Playwright E2E

**CI** (Ubuntu + Windows) and the **PyPI release** workflow run **`npm run test:e2e`** after the production **`static/`** build. One-time browser download locally:

```bash
cd web
npm ci
npx playwright install chromium
npm run test:e2e
```

**`playwright.config.ts`** starts **`scripts/e2e-server.mjs`**: a fresh workspace under **`.tmp/playwright-fd-workspace/`**, then **`flightdeck serve`** on **`http://127.0.0.1:9876`**. When **`uv`** is on **`PATH`** and the repo has **`uv.lock`**, the server uses **`uv run flightdeck …`** (same as CI) so Playwright loads **this repo’s** package and committed **`static/`** bundle—not an unrelated **`pip install`**. Override with **`FLIGHTDECK_E2E_USE_UV=0`** to force the Python fallback; that fallback sets **`PYTHONPATH`** to **`../src`** so **`python -m flightdeck.cli.main`** resolves the workspace checkout.

The default **`npm run test:e2e`** suite expects **`promotion_requires_approval: false`** and **`pricing_catalog_configured: false`** in that workspace; **`e2e-server.mjs`** runs **`flightdeck init --no-bundled-pricing`** so the probe matches **`e2e/smoke.spec.ts`**. A stray shell **`FD_E2E_FORCE_APPROVAL=1`** does **not** flip the server by itself: **`e2e-server.mjs`** only patches YAML when **`PW_FORCE_APPROVAL_WORKSPACE=1`**, which **`playwright.config.ts`** sets when the Playwright CLI lists **exactly one** `e2e/*.spec.ts` argument and it is **`e2e/actions-approval.spec.ts`**. Run approval tests with **`FD_E2E_FORCE_APPROVAL=1 npx playwright test e2e/actions-approval.spec.ts`** (that single-file form both enables the approval workspace and un-skips the describe block). Do not pass **`e2e/actions-approval.spec.ts`** together with other spec paths unless you intend a split server mode (the server is one workspace for the whole run).

Run **`npm`** commands from this **`web/`** directory (repo root is one level up: **`cd web`**).

## App architecture

The React app uses **HashRouter** (`#/` paths) so it works without server-side routing from FastAPI's static file mount.

| Route | Component | Purpose |
|-------|-----------|---------|
| `#/` | `OverviewPage` | Releases table, promoted pointers, recent audit actions |
| `#/diff` | `DiffPage` | Run-diff form; calls `POST /v1/diff` |
| `#/actions` | `ActionsPage` | `GET /v1/workspace` then promote / rollback (direct **`POST /v1/promote`** or request/confirm when approval is on) |

**Shell and context:** `AppShell` wraps all pages in a `TimelineRefreshProvider`. When a promote/rollback mutation succeeds in `ActionsPage`, it calls `notifyTimelineMutated()`. `OverviewPage` watches the `generation` counter and re-fetches automatically — no page reload needed.

**`src/api.ts`:** `fetchJson<T>` handles auth (`VITE_FLIGHTDECK_LOCAL_API_TOKEN` → `Authorization: Bearer …`), error extraction, and the common `throw on non-ok` pattern. `loadTimeline()` fans out to `GET /v1/releases`, `GET /v1/promoted`, and `GET /v1/actions` in parallel and merges the results into a single `TimelinePayload`.

Full reference (pages, context, API helpers, CSS tokens): **[`docs/web-ui.md`](../docs/web-ui.md)**.
