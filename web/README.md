# FlightDeck web UI (React + Vite)

Source for the local UI served by **`flightdeck serve`** at **`/`**. Production bundles are emitted to **`../src/flightdeck/server/static/`** (FastAPI serves **`index.html`** and hashed files under **`/assets/`**).

## Commands

```bash
cd web
npm ci
npm run build
```

After any change under **`web/src/`**, run **`npm run build`** again and commit the updated **`src/flightdeck/server/static/`** tree. **CI** rebuilds and runs **`git diff --exit-code`** on that path so committed assets cannot drift.

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

## PR split (subagent-friendly)

**Already landed:** Vite + React + TS **`web/`**, committed **`static/`**, FastAPI **`/assets`** mount, CI **`npm run build`** + **`git diff --exit-code`** on **`static/`**, Playwright smoke, LF normalization via **`.gitattributes`** (stable **`git diff`** on Windows).

**Suggested follow-ups:**

1. **PR B — UI behavior**  
   Timeline UX (tables, loading states, `/v1/actions` query filters), mutation UX (inline errors, disable buttons while pending). Touch **`web/src/`** only, then **`npm run build`** and commit **`static/`**.

   *Subagent prompt:* “Improve **`web/src/App.tsx`** (and small new components under **`web/src/`**) for timeline and promote/rollback UX only; rebuild **`static/`**; do not change Python HTTP contracts.”

2. **PR C — Optional**  
   React Router, richer diff visualization, shared design tokens. (**Playwright** smoke is under **`e2e/`**; see **Playwright E2E** above.)

**Parallel subagents for PR B** (non-overlapping files if you split components first):

- **Agent 1 — Read path:** `TimelinePanel` (or equivalent) + styles for releases/promoted/actions.
- **Agent 2 — Write path:** `DiffPanel` + `MutationPanel` + token-aware **`fetch`** helpers.

Rebase one branch onto the other, run **`npm run build` once**, fix any conflicts in **`static/`**, then push.
