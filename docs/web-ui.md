# FlightDeck web UI reference

Strategic UI priorities and UX intent live in **[ROADMAP.md](../ROADMAP.md#web-ui-and-operator-experience)**; this document is the **technical** reference (routes, components, build flags).

`flightdeck serve` serves the React app at `/`. It is built from **`web/`** and the committed
production bundle lives under **`src/flightdeck/server/static/`**.

For setup, dev workflow, build commands, and Playwright E2E instructions see
**[`web/README.md`](../web/README.md)**.

---

## Theming and brand alignment

### Desired state (disclaimer)

The **[README product overview](../README.md#product-overview)** image is a **marketing composite**: dark chrome, dense “dashboard” cards, and narrative labels that **do not** map one-to-one to shipped pages. The bundled **hex mark** (`web/public/flightdeck-icon.png`) matches that art direction (cyan–purple accent, dark ground). **This document and the operator UI** stay grounded in real **`/v1/*`** data—visual work should **not** invent panels (for example a synthetic “release blocked” hero) until the APIs and product decisions exist.

### What we can borrow from the art (incremental)

| Art direction | Application in this repo |
|---------------|---------------------------|
| Dark navy / near-black shell | **`html[data-theme="dark"]`** in `web/src/index.css` mirrors semantic tokens; **Appearance** control in the sidebar defaults to **Light** (stored under **`localStorage`** key **`flightdeck-theme`**). |
| Cyan → purple gradient | CSS variables (for example `--fd-accent-gradient`) for **active nav**, **primary buttons**, and **focus-visible** accents—used sparingly so trust/safety UI stays calm. |
| High-contrast titles | Tune `--fd-type-*` and weights under dark mode; avoid shrinking body text for density. |
| “Neon” feel | Reserve for **interactive** states, not large background fills. |
| Geometric sans | **Shipped:** offline **system UI stack** in `index.css` (`--fd-font`). Optional: install **Inter** locally if you want that face without bundling remote CSS. |

### Phased implementation plan

1. **Token foundation** — Extend `:root` with any missing semantics (`--fd-surface-elevated`, gradient stops, optional `--fd-bg-subtle`). Replace scattered literals in `web/src/index.css` (for example warning callout backgrounds) with variables so dark mode does not require hunting hex values.
2. **`[data-theme="dark"]` block** — Mirror every semantic token used by `.fd-shell`, sidebar, cards, tables, `Badge`, drawers, and `JsonPanel`; set `color-scheme: dark` on `html` when active. Validate **WCAG AA** for body text and links.
3. **Preference UI** — **`/#/settings`** (and room for more prefs later): **Light** / **Dark** / **System**; listen to `prefers-color-scheme` when System is selected. Persist `localStorage` key **`flightdeck-theme`** (`light` \| `dark` \| `system`).
4. **Brand accents** — Apply the gradient token to **active** `.fd-nav__link--active` (left rail) and primary submit-style buttons; keep destructive actions on existing red semantics.
5. **Light theme polish** — Even before dark ships: align spacing rhythm and card shadows with the same tokens so both themes stay maintainable.
6. **Verification** — From `web/`: **`npm ci`**, **`npm run build`**, commit **`src/flightdeck/server/static/`**; **`npm run test:e2e`** (includes **`e2e/theme.spec.ts`**: default light, dark persistence, system / `prefers-color-scheme`, overview smoke in dark). Manually smoke **Diff** and **Actions** in both themes (policy panels, JSON drawer, rollback affordances).

### Explicit deferrals (still)

- **Multi-theme marketplaces**, per-user arbitrary color pickers, or third-party skin systems — off mission.
- **Infographic-only widgets** (staged DEV→STAGING→PROD pipeline strip, sparkline grids) — wait for real APIs and **[ROADMAP](ROADMAP.md)** operator outcomes, not decorative parity with the poster.

---

## Routing

The app uses **HashRouter** (`react-router-dom`) so all navigation stays within the single
`index.html` that FastAPI's static file mount serves. URLs look like
`http://127.0.0.1:8765/#/diff`. No server-side route matching is required.

**Static UI assets:** hashed bundles are mounted at **`/assets/`**. The sidebar mark and tab icons use the **bundled** URL from `web/src/assets/flightdeck-icon.png` (emitted as **`/assets/flightdeck-icon-<hash>.png`**; `main.tsx` sets `<link rel="icon">` at runtime). A **stable** duplicate remains at **`GET /flightdeck-icon.png`** (from `web/public/` at build time + FastAPI `FileResponse`) for bookmarks, probes, and **`web/e2e/smoke.spec.ts`**.

**Typography:** the UI uses an **offline-first system font stack** (no Google Fonts or other remote CSS). Install **Inter** locally if you want that face in dev tools without changing the bundle.

| Hash path | Component | HTTP calls | Notes |
|-----------|-----------|-----------|-------|
| `#/` | `OverviewPage` | `GET /v1/releases`, `GET /v1/promoted`, `GET /v1/actions`, `GET /v1/metrics` | `ReleaseLifecycleStrip` + optional `?release=` hero; promoted table first; releases table with filter row and copy/diff shortcuts; collapsible ledger metrics; **auto-refresh** every 30 s while tab is visible + on timeline **`generation`** bump |
| `#/diff` | `DiffPage` | `POST /v1/diff` | URL params prefill form (`baseline`, `candidate`, `window`, `environment`); result rendered through `DiffVerdictStack` → `DiffReleaseTwin` → `DiffPolicyPanel` → `DiffChangeImpact` (with collapsible `DiffPricingExpand`) → `DiffDecisionCard` + **Continue to promote** link → raw JSON panel |
| `#/runs` | `RunsPage` | `GET /v1/releases` (for datalist), `GET /v1/runs`, `GET /v1/runs/export` | Forensics: filters, table (trace/status, trace band rows or **Group by trace_id**), **View** drawer (focus trap, session/span ids), typed **run-query error** card with **Retry**, empty/offset/truncation hints, NDJSON download |
| `#/settings` | `SettingsPage` | *(none)* | **Color theme** (Light / Dark / System) via `ThemeToggle`; more preferences later. |
| `#/actions` | `ActionsPage` | `GET /v1/workspace`, `GET /v1/promotion-requests` (when `promotion_requires_approval`), `POST /v1/promote` **or** `POST /v1/promote/request` + `POST /v1/promote/confirm`, `POST /v1/rollback` | URL params prefill form (`release_id`, `environment`, `window`); workspace skeleton then strip; approval path: numbered steps, pending **Refresh list** / **Use for confirm**; **Rollback** danger-styled |
| `#/*` (any other) | — | Redirects to `#/` | |

`App.tsx` declares the route tree. `AppShell` is the layout wrapper rendered for all routes.

When `VITE_FLIGHTDECK_UI_READ_ONLY=true` is set at build time, the `#/actions` route
renders a `<Navigate to="/" replace />` rather than `ActionsPage`, and the nav link for
**Promote** is suppressed. The read-only mode is for demos and shared screens where
promote/rollback capability should be unavailable regardless of network placement.

---

## Component tree

```
ThemePreferenceProvider (`App.tsx`)
└── HashRouter
    └── Routes / AppShell layout route
        └── TimelineRefreshProvider
            └── div.fd-shell
                ├── aside.fd-sidebar (brand, collapse chevron, primary nav, footer nav → Settings)
                └── div.fd-shell__content
                    ├── SecurityStatusBar
                    └── main#main-content
                        ├── OverviewPage
                        │   ├── ReleaseLifecycleStrip
                        │   └── focused release hero (when ?release= is set)
                        ├── DiffPage
                        │   ├── DiffVerdictStack
                        │   ├── DiffReleaseTwin
                        │   ├── DiffPolicyPanel
                        │   ├── DiffChangeImpact → DiffPricingExpand
                        │   ├── DiffDecisionCard
                        │   └── JsonPanel
                        ├── RunsPage
                        ├── ActionsPage
                        └── SettingsPage
```

---

## `AppShell` (`web/src/components/AppShell.tsx`)

Renders a fixed-width **left sidebar** (`aside.fd-sidebar`) with brand (gradient **FlightDeck** wordmark, mark in a **raised tile**), a **collapse** control (SVG chevrons, `localStorage` **`flightdeck-sidebar-collapsed`**), a **primary** nav (inline SVG icons + labels; icon-only when collapsed), and a **footer** nav pinned to the bottom of the rail with **Settings** → `#/settings`. Then a **`fd-shell__content`** column with `SecurityStatusBar` and
`<main>` wrapping an `<Outlet>` for the active page. On narrow viewports the sidebar stacks
above the content with a horizontal nav row; a **collapsed** rail is expanded back to full labels in that breakpoint. Wraps the subtree in `TimelineRefreshProvider`
so any descendant can access the refresh context. `ThemePreferenceProvider` (from `App.tsx`) wraps the router so `ThemeToggle` on **Settings** can read and update **`flightdeck-theme`**; `main.tsx` applies the effective theme before the first paint to avoid a flash of the wrong scheme.

A **Skip to main content** link (class `fd-skip-link`) appears first in the shell; it uses
`preventDefault` + `focus()` on `#main-content` so **HashRouter** hash URLs (`#/…`) are not
replaced by a fragment-only `href`.

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

Mounted by `AppShell` at the top of the main content column (below the sidebar on wide
layouts). Fetches `GET /health`
on mount to read `mutation_auth` and `read_auth` (`"bearer"` / `"loopback"` and `"bearer"` / `"open"`), then renders an info or
warning strip:

| Condition | What is shown |
|-----------|---------------|
| `UI_READ_ONLY=true` | Info banner: "Read-only UI: navigation to promote and rollback is disabled." |
| `/health` in flight | Muted line + skeleton; **`aria-busy="true"`** on the strip |
| `/health` fetch failed | Warning banner: "Could not load server security mode." (with error detail) |
| `mutation_auth === null` (unknown value) | Nothing (renders `null`) |
| Server `"bearer"` + client has no token | **Warning**: token mismatch — promote/rollback will be rejected until the UI token matches the server |
| Normal (no mismatch) | Info strip with two lines: server mode description and client token status |

The component never displays the token value itself. It uses the `role="status"` ARIA role
for live-region accessibility.

**Token mismatch detection:** when the server uses a Bearer token (`mutation_auth` is `"bearer"`) and
`clientMutationTokenConfigured()` is `false`, the strip warns that API requests will
fail. This is a configuration hint only — the server enforces the actual gate.

---

## `OverviewPage` (`web/src/pages/OverviewPage.tsx`)

Read-only dashboard. Layout:

1. **`ReleaseLifecycleStrip`** — horizontal workflow guide showing the four stages
   (Register → Ingest → Diff & policy → Promote & rollback) as linked steps. Each step
   links to the relevant page; the Promote step is static (no link) in read-only builds.
   Includes a note that deep links prefill forms but do not auto-submit.

2. **Focused release hero** — when `?release=<release_id>` is present in the URL, a hero
   section appears above the tables. It shows agent, version, environment, abbreviated
   release ID (with **Copy ID** button), checksum, and the current promoted baseline for
   that agent/environment pair (or a note that no pointer exists). Action buttons link to
   Diff, Runs, and Promote with the release, environment, and a default `7d` window
   pre-filled. A **Clear focus** button removes the `?release=` param. If the ID does not
   match any registered release, a warning is shown instead.

3. **Promoted releases table** — lists current `(agent_id, environment)` → `release_id`
   pointers. Each row has a **View** link to `#/?release=<id>` to focus that release.

4. **Releases table** — lists all registered releases with Agent, Version, Environment, ID,
   Checksum, and Created columns. A **Status** badge shows **Live** (the release matches the
   current promoted pointer for that agent/environment) or **Registered**. A filter row
   (agent substring, environment substring, and Live / Not live / All dropdown) reduces the
   table without re-fetching. **Copy** buttons (via `CopyTextButton`) copy the release ID.
   Each row has a **Diff** shortcut (links to `#/diff` with baseline = promoted pointer,
   candidate = this release, environment and `7d` window pre-filled) and a **Focus** link.

5. **Recent actions table** — promote/rollback audit rows: When, Action, Policy badge,
   Release, Environment, Reason.

6. **Ledger metrics** — collapsible panel (collapsed by default, toggle via button). Shows
   raw counters from `GET /v1/metrics`: releases, pricing tables, run events, promoted
   pointers, actions totals + breakdown, `schema_version`, `generated_at`.

Long IDs are abbreviated with `shortId(id, keepStart, keepEnd)` and shown in full on hover
via the HTML `title` attribute.

**URL params for OverviewPage:**

| Param | Effect |
|-------|--------|
| `?release=<id>` | Activates the focused release hero. The releases table filter and tables remain visible below. |

**Refresh:** while the document tab is visible, the page **auto-polls** metrics and the
timeline every 30 s and uses **silent** fetches after the first load. The `generation`
counter from `TimelineRefreshContext` triggers an immediate refresh after mutations from
`ActionsPage`.

---

## `DiffPage` (`web/src/pages/DiffPage.tsx`)

Form-based interface for `POST /v1/diff`. The page reads initial field values from URL
search params and writes them back on each submission, enabling **deep links** that
pre-fill the form:

| URL param | Form field | Default |
|-----------|-----------|---------|
| `baseline` | Baseline release ID | (empty) |
| `candidate` | Candidate release ID | (empty) |
| `window` | Time window | `7d` |
| `environment` | Environment | `local` |

Example: `#/diff?baseline=rel_abc&candidate=rel_xyz&window=7d&environment=production`

`tenant_id` and `task_id` are **not exposed** in the UI form. To run a diff narrowed to a
specific tenant or task, use the CLI (`flightdeck release diff --tenant <id> --task <id>`)
or call `POST /v1/diff` directly with the `tenant_id` and `task_id` fields. See
[http-api.md § POST /v1/diff](http-api.md#post-v1diff) and
[operations-and-policy.md § compute_diff vs. promote_release filter scope](operations-and-policy.md#compute_diff-vs-promote_release--rollback_release-filter-scope)
for details on what those filters affect.

On submit, the response is parsed via helpers in `diffPayload.tsx` and rendered through a
sequence of dedicated components:

1. **`DiffVerdictStack`** — full-width strip at the top. Shows a **Blocked** banner with the
   first policy reason when policy fails, then a **verdict strip** (green PASS / red FAIL
   with a short narrative). If the diff response contains no `policy` block, a warning is
   shown instead.
2. **`DiffReleaseTwin`** — side-by-side baseline vs candidate IDs, environment, window, and
   resolved `provider/version model` lines from each side's pricing block.
3. **`DiffPolicyPanel`** — card showing the policy PASS/FAIL badge, `evaluated_at`
   timestamp, and full reasons list.
4. **`DiffChangeImpact`** — card with three sub-sections:
   - **Sample coverage** — baseline/candidate run counts and confidence label (with `confidence_reason` when present).
   - **Cost and quality rollups** — `DiffMetric` cards for cost/run (USD), latency avg (ms), error rate, each with baseline → candidate and delta.
   - **`DiffPricingExpand`** — collapsible pricing & model section (collapsed on each new diff result). Shows baseline vs candidate `provider/version model` inline. Expands to reveal: provider/version skew warning, `pricing.warnings` list, `pricing.hints` list, pricing catalog detail (when enabled), and per-1k token prices (input/output, baseline → candidate) when all four rates are present and pricing changed.
5. **`DiffDecisionCard`** — summarizes the gate outcome in plain English and, when policy
   passes and the candidate release ID is known, shows a **Continue to promote** link to
   `#/actions` with `release_id`, `environment`, and `window` pre-filled.
6. **Raw diff JSON** panel (`JsonPanel`, collapsed by default).

The **Compute diff** button is disabled while the request is in flight (`busy` state).
Errors from the API are shown as an inline `fd-alert--error` element.

Note: `POST /v1/diff` is a **read-only computation** and does not require a mutation
token. See [http-api.md](http-api.md) for the full response schema.

### Diff component subtree

```
DiffPage
├── DiffVerdictStack          (full-width verdict/block strip)
├── DiffReleaseTwin           (baseline vs candidate identity, env, pricing line)
├── DiffPolicyPanel           (policy badge + reasons)
├── DiffChangeImpact          (samples, metric rollups, expandable pricing)
│   └── DiffPricingExpand     (collapsed; shows per-1k prices, warnings, catalog)
├── DiffDecisionCard          (verdict copy + "Continue to promote" link)
└── JsonPanel                 (raw diff JSON, collapsed by default)
```

Shared data extraction: `web/src/components/diff/diffPayload.tsx` exports typed helpers
(`pickPolicy`, `pickPricing`, `pricingLine`, `DiffMetric`) that isolate JSON traversal from
rendering.

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

**Auth:** `VITE_FLIGHTDECK_LOCAL_API_TOKEN` is sent on every `fetchJson` call, including **`POST /v1/promote/request`** and **`POST /v1/promote/confirm`**. It must **match** `FLIGHTDECK_LOCAL_API_TOKEN` on the server when the server enforces Bearer (see [http-api.md § Authentication](http-api.md#authentication-and-access-control)). FlightDeck does **not** mint this value: the operator chooses a shared secret for **HTTP API** access. It is baked in at **build time** for the committed static bundle; local Bearer testing normally uses **`web/.env.local`** + **`npm run dev`**. It is **not** OAuth or end-user SSO — see [SECURITY.md](../SECURITY.md) (**Local HTTP API**).

**HTTP errors:** `fetchJson` formats FastAPI **`detail`** strings, validation arrays, and `{ message: … }` objects into a single `Error` message for the alert line.

---

## `urlSearch.ts` (`web/src/urlSearch.ts`)

Helpers for hash-router deep-linking. Both `DiffPage`, `OverviewPage`, `RunsPage`, and
`ActionsPage` use these to read from and write to `URLSearchParams`:

| Export | Description |
|--------|-------------|
| `pickTrimmedSearch(searchParams, key)` | Returns `searchParams.get(key)?.trim() ?? ""`. Never returns `null`. |
| `searchParamsFromRecord(rec)` | Builds a `?key=value` string from a `Record<string, string>`, omitting entries with empty values. Returns `""` when all values are empty. |

**Deep-link examples:**

| Page | URL | Effect |
|------|-----|--------|
| Overview | `#/?release=rel_abc123` | Activates focused release hero |
| Diff | `#/diff?baseline=rel_a&candidate=rel_b&window=7d&environment=production` | Pre-fills the diff form |
| Runs | `#/runs?release_id=rel_abc&window=24h&environment=staging` | Pre-fills release and filters |
| Actions | `#/actions?release_id=rel_abc&environment=production&window=7d` | Pre-fills promote/rollback form |

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
  read_auth?: "bearer" | "open";
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

### `CopyTextButton` (`web/src/components/CopyTextButton.tsx`)

Inline button that copies a string to the clipboard. Uses `navigator.clipboard.writeText`
with an `execCommand` fallback for headless or insecure contexts (so Playwright E2E tests
also work). Status cycles through `idle → "Copied" → idle` (2 s) or `idle → "Failed" →
idle` (2.5 s). Props:

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `label` | string | — | Accessible label prefix (e.g. `"Release ID"`) |
| `value` | string | — | String to copy |
| `buttonText` | string | `"Copy"` | Visible button text when idle |
| `className` | string | `"fd-btn fd-btn--ghost fd-copy-btn"` | CSS class |
| `testId` | string | — | Optional `data-testid` for E2E |

### `ReleaseLifecycleStrip` (`web/src/components/ReleaseLifecycleStrip.tsx`)

Horizontal `<nav>` rendered at the top of `OverviewPage`. Shows four workflow steps:
**Register** → **Ingest** → **Diff & policy** → **Promote & rollback**, each linking to
the relevant page. In read-only builds the **Promote & rollback** step becomes a static
`<span>` with a "not available in read-only UI" title. The strip includes a short note
that deep links prefill forms on target pages but do not auto-submit them.

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
| `--fd-bg` | Main column page background |
| `--fd-surface` | Card / sidebar rail background |
| `--fd-sidebar-width` | Width of the left navigation rail (wide layouts) |
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
| `fd-shell` | Full-height row: sidebar + main column |
| `fd-sidebar` | Left rail: brand block + `fd-sidebar__nav` primary links |
| `fd-shell__content` | Flex column: security strip + `fd-main` |
| `fd-nav__link` | Sidebar nav link; `--active` modifier (accent left border) |
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
| `fd-security-strip` | Strip at top of main column; wraps `SecurityStatusBar` output |
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
| `fd-lifecycle-strip` | `ReleaseLifecycleStrip` nav container |
| `fd-lifecycle-strip__step` | Individual step `<li>`; includes `__arrow`, `__link`, `__label`, `__hint` children |
| `fd-release-hero` | Focused release hero section on `OverviewPage` (activated by `?release=`) |
| `fd-release-hero__title` | Agent + version heading inside the hero |
| `fd-release-hero__meta` | Abbreviated IDs, checksum, and baseline pointer line |
| `fd-release-hero__actions` | Row of quick-action buttons (Diff, Runs, Promote, Clear focus) |
| `fd-diff-block-strip` | Full-width error strip for the first policy block reason (above the verdict) |
| `fd-diff-verdict-strip` | Full-width verdict strip; `--pass` (green) / `--fail` (red) modifiers |
| `fd-diff-twin` | `DiffReleaseTwin` container; `__grid`, `__col`, `__label`, `__id`, `__detail` children |
| `fd-policy-panel` | `DiffPolicyPanel` card |
| `fd-decision-card` | `DiffDecisionCard` card |
| `fd-diff-stack` | Stack container inside `DiffChangeImpact` |
| `fd-diff-section` | Sub-section inside `DiffChangeImpact`; `--collapse-wrap` for the expandable pricing row |
| `fd-diff-section__title` | Section heading inside `fd-diff-stack` |
| `fd-diff-section__body` | Section body text |
| `fd-diff-pricing-inline` | Inline row for pricing summary + expand toggle |
| `fd-copy-btn` | Default class on `CopyTextButton` (ghost button with icon affordance) |
| `fd-table--hover` | Adds row hover accent to `fd-table` |
| `fd-table-toolbar` | Filter row above a table inside `fd-card` |

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
