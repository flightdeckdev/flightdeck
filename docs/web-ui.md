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

| Hash path | Component | HTTP calls | Notes |
|-----------|-----------|-----------|-------|
| `#/` | `OverviewPage` | `GET /v1/releases`, `GET /v1/promoted`, `GET /v1/actions`, `GET /v1/metrics` (parallel where applicable) | Ledger metrics card is read-only counters |
| `#/diff` | `DiffPage` | `POST /v1/diff` | Renders `pricing.warnings`, optional **`pricing.catalog`** / **`pricing.hints`**, per-1k prices when present |
| `#/runs` | `RunsPage` | `GET /v1/releases` (for datalist), `GET /v1/runs`, `GET /v1/runs/export` | Forensics: filters, table, NDJSON download |
| `#/actions` | `ActionsPage` | `GET /v1/workspace`, `GET /v1/promotion-requests` (when `promotion_requires_approval`), `POST /v1/promote` **or** `POST /v1/promote/request` + `POST /v1/promote/confirm`, `POST /v1/rollback` | Workspace strip shows server version + mode; see **ActionsPage** below |
| `#/*` (any other) | — | Redirects to `#/` | |

`App.tsx` declares the route tree. `AppShell` is the layout wrapper rendered for all routes.

When `VITE_FLIGHTDECK_UI_READ_ONLY=true` is set at build time, the `#/actions` route
renders a `<Navigate to="/" replace />` rather than `ActionsPage`, and the nav link for
**Promote** is suppressed. The read-only mode is for demos and shared screens where
promote/rollback capability should be unavailable regardless of network placement.

---

## Component tree

```
App (HashRouter)
└── AppShell (layout: header + nav)
    └── TimelineRefreshProvider (context)
        ├── SecurityStatusBar (below header, above main content)
        ├── OverviewPage  (route: #/)
        ├── DiffPage      (route: #/diff)
        ├── RunsPage      (route: #/runs)
        └── ActionsPage   (route: #/actions; redirects → #/ when UI_READ_ONLY)
```

---

## `AppShell` (`web/src/components/AppShell.tsx`)

Renders the top header with brand name and primary nav links, then an `<Outlet>` for the
active page. Wraps the entire subtree in `TimelineRefreshProvider` so any descendant can
access the refresh context. Mounts `SecurityStatusBar` between the header and the main
content area.

Nav links use `NavLink` from `react-router-dom` with an `fd-nav__link--active` class applied
when the route is active. The **Promote** nav link is suppressed when `UI_READ_ONLY` is
`true` (see [`uiConfig.ts`](#uiconfigts-websrcuiconfigts) below).

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

**Data flow for a successful direct promote** (when `promotion_requires_approval` is **false** in `flightdeck.yaml`):

1. User fills the `ActionsPage` form and clicks **Promote**.
2. `ActionsPage` calls `fetchJson` → `POST /v1/promote`.
3. On success, `notifyTimelineMutated()` is called.
4. `OverviewPage` (mounted in the same shell) sees `generation` change via context.
5. `useEffect` fires `loadTimeline()` and re-renders tables with fresh data.

When **`promotion_requires_approval`** is **true**, step 2 uses **`POST /v1/promote/request`** instead; confirm uses
**`POST /v1/promote/confirm`** from the same page. `GET /v1/workspace` on mount drives which buttons are shown.

---

## `uiConfig.ts` (`web/src/uiConfig.ts`)

Build-time configuration helpers read from `import.meta.env`:

| Export | Type | Description |
|--------|------|-------------|
| `UI_READ_ONLY` | `boolean` | `true` when `VITE_FLIGHTDECK_UI_READ_ONLY === "true"`. Hides the Promote nav link, redirects `#/actions` to `#/`, and causes `SecurityStatusBar` to show a read-only banner instead of the auth status. |
| `clientMutationTokenConfigured()` | `() => boolean` | Returns `true` when `VITE_FLIGHTDECK_LOCAL_API_TOKEN` is set to a non-empty, non-whitespace string in the build env. Used by `SecurityStatusBar` to detect a mismatch between the server's bearer requirement and the client's token configuration. |

---

## `SecurityStatusBar` (`web/src/components/SecurityStatusBar.tsx`)

Mounted by `AppShell` between the header and the main content area. Fetches `GET /health`
on mount to read `mutation_auth` (`"bearer"` or `"loopback"`), then renders an info or
warning strip:

| Condition | What is shown |
|-----------|---------------|
| `UI_READ_ONLY=true` | Info banner: "Read-only UI: navigation to promote and rollback is disabled." |
| `/health` fetch failed | Warning banner: "Could not load server security mode." (with error detail) |
| `mutation_auth === null` (unknown value) | Nothing (renders `null`) |
| Server `"bearer"` + client has no token | **Warning**: token mismatch — promote/rollback will be rejected until the UI token matches the server |
| Normal (no mismatch) | Info strip with two lines: server mode description and client token status |

The component never displays the token value itself. It uses the `role="status"` ARIA role
for live-region accessibility.

**Token mismatch detection:** when `mutation_auth` is `"bearer"` and
`clientMutationTokenConfigured()` is `false`, the strip warns that mutation requests will
fail. This is a configuration hint only — the server enforces the actual gate.

---

## `OverviewPage` (`web/src/pages/OverviewPage.tsx`)

Read-only dashboard. Renders a **Ledger metrics** card from `fetchMetrics()` plus three tables from `loadTimeline()` output:

| Block | Source | Content |
|-------|--------|---------|
| Ledger metrics | `GET /v1/metrics` | Releases, pricing tables, run events, promoted pointers, and actions totals (plus `actions_by_action` breakdown), `schema_version`, `generated_at` |
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

`tenant_id` and `task_id` are **not exposed** in the UI form. To run a diff narrowed to a
specific tenant or task, use the CLI (`flightdeck release diff --tenant <id> --task <id>`)
or call `POST /v1/diff` directly with the `tenant_id` and `task_id` fields. See
[http-api.md § POST /v1/diff](http-api.md#post-v1diff) and
[operations-and-policy.md § compute_diff vs. promote_release filter scope](operations-and-policy.md#compute_diff-vs-promote_release--rollback_release-filter-scope)
for details on what those filters affect.

On submit, the raw diff response is parsed and rendered as:

- **Summary card:** policy badge (PASS / FAIL), failure reasons list, sample counts and
  confidence label (including `confidence_reason` when present).
- **Pricing table warnings:** when `pricing.warnings` is a non-empty string array, a
  `fd-alert--warn` list is shown above the pricing/model-change banner (diagnostic only).
- **Catalog / hints:** when `pricing.catalog` or `pricing.hints` is present, the UI surfaces
  catalog enabled state, lines, and hint strings (see [pricing-catalog.md](pricing-catalog.md)).
- **Pricing change warning:** when the diff response includes a `pricing` block with
  `pricing_or_model_changed: true`, a `fd-alert--warn` banner is shown in the summary
  card. It names the baseline and candidate provider/version/model so the user knows the
  cost delta includes pricing assumption changes, not just usage changes. When the response
  also includes a `pricing.prices` block with all four per-1k token rates present, the
  banner additionally shows a **Per-1k token prices** line (baseline → candidate, input and
  output separately) so the user can separate tariff moves from token volume changes in the
  cost delta. Rates are rendered to six decimal places via `toFixed(6)`.
- **Metric cards:** cost/run (USD), latency avg (ms), error rate — each showing baseline,
  candidate, and delta.
- **Raw diff JSON** panel (collapsed by default via `JsonPanel`).

The **Compute diff** button is disabled while the request is in flight (`busy` state).
Errors from the API are shown as an inline `fd-alert--error` element.

Note: `POST /v1/diff` is a **read-only computation** and does not require a mutation
token. See [http-api.md](http-api.md) for the full response schema.

---

## `ActionsPage` (`web/src/pages/ActionsPage.tsx`)

On mount, loads **`GET /v1/workspace`** (`fetchWorkspace`) and renders a short status strip:
**`server_version`**, whether a **`pricing_catalog_path`** is configured (**`pricing_catalog_configured`**), and
whether **`promotion_requires_approval`** is on.

Mutation form fields:

| Field | Default | Maps to |
|-------|---------|---------|
| Release ID | (empty) | `release_id` |
| Environment | `local` | `environment` |
| Window | `7d` | `window` |
| Reason (required) | (empty) | `reason` (promote, rollback, and promotion **request**) |

The `actor` field is hardcoded to `"react-ui"` for audit log attribution.

**Direct promotion** (default): **Promote** calls `POST /v1/promote`. **Rollback** always calls `POST /v1/rollback`.

**Approval mode:** **Promote** is replaced by **Request promotion** (`POST /v1/promote/request`). A **Pending promotion requests**
table refreshes from `GET /v1/promotion-requests?status=pending`. **Confirm promotion** posts `POST /v1/promote/confirm` with
`request_id` (prefilled after a successful request) and `approval_reason`. A collapsible **Promotion request (raw JSON)**
panel shows the request response.

All primary actions use `window.confirm`. Buttons are disabled while a request is in flight (`busy` state). Empty
reason / empty confirm fields abort with inline errors.

After a successful **promote** or **rollback** (or **confirm**):

1. The response is parsed by `pickOutcome()` when it matches the promote/rollback outcome contract; otherwise the raw JSON panel opens.
2. Outcome card shows policy badge, pointer badge, metric grid, and reasons list when applicable.
3. `notifyTimelineMutated()` runs so `OverviewPage` refetches.

**Auth:** `VITE_FLIGHTDECK_LOCAL_API_TOKEN` is sent on every `fetchJson` call, including **`POST /v1/promote/request`** and **`POST /v1/promote/confirm`**. See [http-api.md § Authentication](http-api.md#authentication-and-access-control).

**HTTP errors:** `fetchJson` formats FastAPI **`detail`** strings, validation arrays, and `{ message: … }` objects into a single `Error` message for the alert line.

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

type HealthPayload = {
  status: string;
  /** Present on current servers; "bearer" when FLIGHTDECK_LOCAL_API_TOKEN is set. */
  mutation_auth?: "bearer" | "loopback";
};

/** Mirrors the `policy` sub-object in promote/rollback responses and diff responses. */
type PolicyResultPayload = {
  passed: boolean;
  reasons: string[];
  evaluated_at?: string;
};

/**
 * Full HTTP 200 body for `POST /v1/promote` and `POST /v1/rollback`.
 * Mirrors `_action_body()` in `src/flightdeck/server/routes/actions.py`.
 *
 * On HTTP 409 (policy blocked), the server wraps an equivalent object inside
 * `{ detail: { message, outcome } }` where `outcome` has the same shape.
 */
type ActionOutcomePayload = {
  action_id: string;
  action: "promote" | "rollback";
  release_id: string;
  agent_id: string;
  environment: string;
  baseline_release_id: string | null;  // null on first promotion
  promoted_pointer_changed: boolean;
  policy: PolicyResultPayload;
};
```

### `fetchJson<T>(path, init?): Promise<T>`

Thin wrapper around `fetch`:

1. Reads `VITE_FLIGHTDECK_LOCAL_API_TOKEN` from `import.meta.env` and injects an
   `Authorization: Bearer …` header if the env var is non-empty and no `Authorization`
   header is already set.
2. Calls `fetch(path, { ...init, headers })`.
3. On non-2xx, formats `response.json().detail` (string, validation array, or object with `message`) into a readable message and throws `Error(…)`.
4. On JSON parse failure, falls back to `{}` before checking `res.ok`.

### `fetchHealth(): Promise<HealthPayload>`

Calls `fetchJson<HealthPayload>("/health")`. Used by `SecurityStatusBar` to discover the
server's mutation-auth mode (`"bearer"` or `"loopback"`) without exposing secret values.

### `loadTimeline(): Promise<TimelinePayload>`

Fires three `GET` requests in parallel via `Promise.all`:
- `GET /v1/releases` → `{ releases }`
- `GET /v1/promoted` → `{ promoted }`
- `GET /v1/actions` → `{ actions }`

Returns a merged `TimelinePayload`. Used by `OverviewPage` on mount and on every
`generation` increment.

### `fetchWorkspace(): Promise<WorkspacePublicPayload>`

Calls `GET /v1/workspace`. Used by `ActionsPage` on mount.

### `fetchPromotionRequests({ status?, limit? })`

Calls `GET /v1/promotion-requests` with optional query parameters. Used by `ActionsPage` when
`promotion_requires_approval` is true to populate the pending requests table.

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
| `fd-alert` | Inline alert box; `--error`, `--info`, `--warn` modifiers |
| `fd-security-strip` | Full-width strip below the header; wraps `SecurityStatusBar` output |
| `fd-security-strip__msg` | Message paragraph inside the security strip (zero margin) |
| `fd-json-panel` | Collapsible JSON viewer container |
| `fd-metric-grid` | Grid of metric cards for diff output |
| `fd-metric` | Single metric card (label, baseline → candidate, delta) |
| `fd-mono` | Monospace inline span; `--sm` for smaller size |
| `fd-muted` | Secondary text color |
| `fd-nowrap` | `white-space: nowrap` for date/ID cells |
| `fd-empty-cell` | Centered empty-state message in a table cell |
| `fd-inline` | Inline flex row used for label + badge pairs inside card headers |
| `fd-samples` | Muted paragraph for sample/confidence metadata in diff and action outcome cards |
| `fd-reasons` | Small bulleted list of policy failure reasons; used in `DiffPage` and `ActionsPage` outcome cards |

---

## Environment variables

| Variable | Where set | Effect |
|----------|-----------|--------|
| `VITE_FLIGHTDECK_LOCAL_API_TOKEN` | `.env.local` or build env | Injected as `Authorization: Bearer …` on every `fetchJson` call. Must match `FLIGHTDECK_LOCAL_API_TOKEN` on the server when the server token gate is active. |
| `VITE_FLIGHTDECK_UI_READ_ONLY` | `.env.local` or build env | Set to `"true"` to enable read-only mode: hides the Promote nav link, redirects `#/actions` to `#/`, and shows a read-only banner in `SecurityStatusBar`. Intended for demo / shared-screen deployments. |
| `VITE_DEV_PROXY_TARGET` | `.env.local` | Overrides the Vite dev proxy target (default: `http://127.0.0.1:8765`) |

These are **build-time** variables (`import.meta.env`). They are baked into the JavaScript
bundle at build time; the production `static/` bundle does not read them from the server at
runtime.

**Note on whitespace-only tokens:** `VITE_FLIGHTDECK_LOCAL_API_TOKEN` is treated as
unset (and no `Authorization` header is sent) when the value is empty or whitespace only.
The server applies the same whitespace trim to `FLIGHTDECK_LOCAL_API_TOKEN` — a
whitespace-only server token is treated as no token (`mutation_auth: "loopback"`).

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
