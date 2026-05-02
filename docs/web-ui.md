# FlightDeck web UI reference

`flightdeck serve` serves the React app at `/`. It is built from **`web/`** and the committed
production bundle lives under **`src/flightdeck/server/static/`**.

For setup, dev workflow, build commands, and Playwright E2E instructions see
**[`web/README.md`](../web/README.md)**.

---

## Routing

The app uses **HashRouter** (`react-router-dom`) so all navigation stays within the single
`index.html` that FastAPI's static file mount serves. URLs look like
`http://127.0.0.1:8765/#/diff`. No server-side route matching is required.

| Hash path | Component | HTTP calls |
|-----------|-----------|-----------|
| `#/` | `OverviewPage` | `GET /v1/releases`, `GET /v1/promoted`, `GET /v1/actions` (parallel) |
| `#/diff` | `DiffPage` | `POST /v1/diff` |
| `#/actions` | `ActionsPage` | `POST /v1/promote` or `POST /v1/rollback` |
| `#/*` (any other) | — | Redirects to `#/` |

`App.tsx` declares the route tree. `AppShell` is the layout wrapper rendered for all routes.

---

## Component tree

```
App (HashRouter)
└── AppShell (layout: header + nav)
    └── TimelineRefreshProvider (context)
        ├── OverviewPage  (route: #/)
        ├── DiffPage      (route: #/diff)
        └── ActionsPage   (route: #/actions)
```

---

## `AppShell` (`web/src/components/AppShell.tsx`)

Renders the top header with brand name and primary nav links, then an `<Outlet>` for the
active page. Wraps the entire subtree in `TimelineRefreshProvider` so any descendant can
access the refresh context.

Nav links use `NavLink` from `react-router-dom` with an `fd-nav__link--active` class applied
when the route is active.

---

## `TimelineRefreshContext` (`web/src/context/TimelineRefreshContext.tsx`)

Provides a lightweight cross-page coordination signal:

| Export | Description |
|--------|-------------|
| `TimelineRefreshProvider` | Wrap the app (or a subtree) to enable the context |
| `useTimelineRefresh()` | Returns `{ generation, notifyTimelineMutated }` |

**`generation`** — a monotonically incrementing integer. `OverviewPage` declares it as a
`useEffect` dependency, so every increment triggers a fresh `loadTimeline()` fetch.

**`notifyTimelineMutated()`** — call this after any successful promote or rollback. It
increments `generation` via `setGeneration(g => g + 1)` and is memoized with `useCallback`
so it is stable across renders.

Throws if called outside `TimelineRefreshProvider`.

**Data flow for a successful promote:**

1. User fills the `ActionsPage` form and clicks **Promote**.
2. `ActionsPage` calls `fetchJson` → `POST /v1/promote`.
3. On success, `notifyTimelineMutated()` is called.
4. `OverviewPage` (mounted in the same shell) sees `generation` change via context.
5. `useEffect` fires `loadTimeline()` and re-renders tables with fresh data.

---

## `OverviewPage` (`web/src/pages/OverviewPage.tsx`)

Read-only dashboard. Renders three tables from `loadTimeline()` output:

| Table | Source | Columns |
|-------|--------|---------|
| Releases | `GET /v1/releases` | Release ID, Agent, Version, Environment, Checksum, Created |
| Promoted | `GET /v1/promoted` | Agent, Environment, Active release |
| Recent actions | `GET /v1/actions` | When, Action, Policy (PASS/FAIL badge), Release, Environment, Reason |

Long IDs are abbreviated with `shortId(id, keepStart, keepEnd)` and shown in full on hover
via the HTML `title` attribute.

**Refresh:** a manual **Refresh** button in the page header calls `loadTimeline()` directly.
The `generation` counter from `TimelineRefreshContext` also triggers automatic refreshes
after mutations from `ActionsPage`.

---

## `DiffPage` (`web/src/pages/DiffPage.tsx`)

Form-based interface for `POST /v1/diff`. Fields mirror the request body:

| Field | Default | Maps to |
|-------|---------|---------|
| Baseline release ID | (empty) | `baseline_release_id` |
| Candidate release ID | (empty) | `candidate_release_id` |
| Window | `7d` | `window` |
| Environment | `local` | `environment` (sent as `null` when empty) |

On submit, the raw diff response is parsed and rendered as:

- **Summary card:** policy badge (PASS / FAIL), failure reasons list, sample counts and
  confidence label.
- **Metric cards:** cost/run (USD), latency avg (ms), error rate — each showing baseline,
  candidate, and delta.
- **Raw diff JSON** panel (collapsed by default via `JsonPanel`).

The **Compute diff** button is disabled while the request is in flight (`busy` state).
Errors from the API are shown as an inline `fd-alert--error` element.

Note: `POST /v1/diff` is a **read-only computation** and does not require a mutation
token. See [http-api.md](http-api.md) for the full response schema.

---

## `ActionsPage` (`web/src/pages/ActionsPage.tsx`)

Mutation form for promote and rollback. Fields:

| Field | Default | Maps to |
|-------|---------|---------|
| Release ID | (empty) | `release_id` |
| Environment | `local` | `environment` |
| Window | `7d` | `window` |
| Reason (required) | (empty) | `reason` |

The `actor` field is hardcoded to `"react-ui"` for audit log attribution.

Both **Promote** and **Rollback** buttons are disabled while any request is in flight. A
`window.confirm` dialog appears before each mutation. An empty reason field aborts before
any network call with an inline error.

After a successful mutation:
1. The API response JSON is shown in a `JsonPanel` (open by default).
2. `notifyTimelineMutated()` is called, refreshing `OverviewPage` automatically.

**Auth:** When `VITE_FLIGHTDECK_LOCAL_API_TOKEN` is set in the build environment (or
`.env.local` during dev), `fetchJson` adds `Authorization: Bearer <token>` to every request.
This satisfies the `FLIGHTDECK_LOCAL_API_TOKEN` gate on `POST /v1/promote` and
`POST /v1/rollback`. See [http-api.md § Authentication](http-api.md#authentication-and-access-control).

**HTTP 409 handling:** when the server returns 409 (policy blocked), `fetchJson` throws with
the `detail.message` extracted from the response body. The error is shown in the alert
element; the audit ledger entry is still recorded server-side.

---

## `api.ts` (`web/src/api.ts`)

Typed client helpers shared across pages.

### Types

```typescript
type ReleaseRow = {
  release_id: string; agent_id: string; version: string;
  environment: string; checksum: string; created_at: string;
};

type PromotedRow = { agent_id: string; environment: string; release_id: string; };

type ActionRow = {
  action_id: string; action: string; release_id: string; agent_id: string;
  environment: string; baseline_release_id: string | null; reason: string;
  policy_passed: boolean; policy_reasons: string[];
  created_at: string; audit_seq: number | null;
};

type TimelinePayload = { releases: ReleaseRow[]; promoted: PromotedRow[]; actions: ActionRow[]; };
```

### `fetchJson<T>(path, init?): Promise<T>`

Thin wrapper around `fetch`:

1. Reads `VITE_FLIGHTDECK_LOCAL_API_TOKEN` from `import.meta.env` and injects an
   `Authorization: Bearer …` header if the env var is non-empty and no `Authorization`
   header is already set.
2. Calls `fetch(path, { ...init, headers })`.
3. On non-2xx, extracts `response.json().detail` (string or array) and throws `Error(detail)`.
4. On JSON parse failure, falls back to `{}` before checking `res.ok`.

### `loadTimeline(): Promise<TimelinePayload>`

Fires three `GET` requests in parallel via `Promise.all`:
- `GET /v1/releases` → `{ releases }`
- `GET /v1/promoted` → `{ promoted }`
- `GET /v1/actions` → `{ actions }`

Returns a merged `TimelinePayload`. Used by `OverviewPage` on mount and on every
`generation` increment.

---

## Shared components

### `Badge` (`web/src/components/Badge.tsx`)

```tsx
<Badge tone="pass">PASS</Badge>
<Badge tone="fail">FAIL</Badge>
<Badge tone="neutral">—</Badge>
```

Renders a `<span>` with the appropriate `fd-badge--{tone}` class. Used in action tables and
diff summary.

### `JsonPanel` (`web/src/components/JsonPanel.tsx`)

Collapsible raw-JSON viewer. Props:

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `title` | string | `"Raw JSON"` | Button label |
| `value` | string | — | JSON string to display in a `<pre>` |
| `defaultOpen` | boolean | `false` | Whether expanded on first render |

Uses `aria-expanded` and `aria-controls` for accessibility. Toggle state is local (`useState`).

---

## CSS design tokens (`web/src/index.css`)

All tokens are CSS custom properties on `:root`:

| Token | Purpose |
|-------|---------|
| `--fd-bg` | Page background |
| `--fd-surface` | Card / header background |
| `--fd-surface-2` | Secondary surface (hover, code blocks) |
| `--fd-border` | Standard border |
| `--fd-border-strong` | Input and button borders |
| `--fd-text` | Primary text |
| `--fd-muted` | Secondary / label text |
| `--fd-accent` | Primary action color (buttons, links) |
| `--fd-accent-hover` | Hover state for accent |
| `--fd-pass-bg` / `--fd-pass-fg` | PASS badge colors |
| `--fd-fail-bg` / `--fd-fail-fg` | FAIL badge colors |
| `--fd-radius` | Standard border radius |
| `--fd-radius-sm` | Small border radius |
| `--fd-shadow` | Card box shadow |
| `--fd-font` | System sans-serif stack |
| `--fd-mono` | Monospace stack |

### Key utility classes

| Class | Description |
|-------|-------------|
| `fd-shell` | Full-height flex container for header + main |
| `fd-header` | Sticky top bar |
| `fd-nav__link` | Navigation link; `--active` modifier for current route |
| `fd-main` | Page content area with max-width and padding |
| `fd-page-head` | Flex row with title/subtitle and optional action button |
| `fd-card` | White surface card with border and shadow |
| `fd-card__head` | Card header row (title + optional inline elements) |
| `fd-table` | Full-width table with hover rows |
| `fd-table-wrap` | Horizontally scrollable table container |
| `fd-badge` | Inline status chip; `--pass`, `--fail`, `--neutral` modifiers |
| `fd-btn` | Base button; `--primary` (accent fill), `--ghost` (borderless) |
| `fd-form-grid` | CSS Grid layout for form fields |
| `fd-field` | Label + input pair; `--full` modifier spans both grid columns |
| `fd-input` | Styled text input |
| `fd-alert` | Inline alert box; `--error` modifier |
| `fd-json-panel` | Collapsible JSON viewer container |
| `fd-metric-grid` | Grid of metric cards for diff output |
| `fd-metric` | Single metric card (label, baseline → candidate, delta) |
| `fd-mono` | Monospace inline span; `--sm` for smaller size |
| `fd-muted` | Secondary text color |
| `fd-nowrap` | `white-space: nowrap` for date/ID cells |
| `fd-empty-cell` | Centered empty-state message in a table cell |

---

## Environment variables

| Variable | Where set | Effect |
|----------|-----------|--------|
| `VITE_FLIGHTDECK_LOCAL_API_TOKEN` | `.env.local` or build env | Injected as `Authorization: Bearer …` on every `fetchJson` call |
| `VITE_DEV_PROXY_TARGET` | `.env.local` | Overrides the Vite dev proxy target (default: `http://127.0.0.1:8765`) |

These are **build-time** variables (`import.meta.env`). They are baked into the JavaScript
bundle at build time; the production `static/` bundle does not read them from the server at
runtime.

---

## Adding a new page

1. Create `web/src/pages/MyPage.tsx` with a named export `MyPage`.
2. Add a route in `web/src/App.tsx`:
   ```tsx
   <Route path="my-page" element={<MyPage />} />
   ```
3. Add a `NavLink` in `web/src/components/AppShell.tsx`.
4. Use `fetchJson` from `../api` for HTTP calls and `useTimelineRefresh` if the page
   performs mutations.
5. Rebuild: `npm run build` from `web/`, then verify `git diff --exit-code src/flightdeck/server/static/` is clean and commit.
