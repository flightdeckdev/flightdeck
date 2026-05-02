# FlightDeck Web UI

`flightdeck serve` ships a local browser UI at `http://127.0.0.1:8765/` (same host and
port as the HTTP API). The UI is a single-page React application served as static files
under `src/flightdeck/server/static/` — no separate Node process is needed at runtime.

## Starting the UI

```bash
flightdeck serve                         # http://127.0.0.1:8765
flightdeck serve --port 9000            # custom port
flightdeck serve --host 0.0.0.0         # non-loopback (prints warning; see SECURITY.md)
```

The server requires a `flightdeck.yaml` in the working directory. Run `flightdeck init`
if it does not exist.

Open `http://127.0.0.1:8765` in your browser after starting the server.

---

## Navigation

The shell has a persistent header with three nav links:

| Link | Hash route | Page |
|------|-----------|------|
| **Overview** | `/#/` | Registered releases, current promotion pointers, recent audit actions |
| **Diff** | `/#/diff` | Interactive release diff (same contract as `flightdeck release diff`) |
| **Promote** | `/#/actions` | Promote or rollback a release |

Navigation uses a hash router so deep-linking works without server-side routing
configuration (`/#/diff`, `/#/actions`).

---

## Overview page

Shows three tables loaded from the API on every page visit:

- **Releases** — all releases registered in this workspace (`GET /v1/releases`).
  Displays `release_id`, agent, version, environment, checksum, and creation time.
  Long IDs are truncated with a `title` tooltip showing the full value.

- **Promoted** — the currently promoted release for each agent/environment pair
  (`GET /v1/promoted`).

- **Recent actions** — promotion and rollback attempts from the audit ledger
  (`GET /v1/actions`, default limit 50). Each row shows when the action occurred,
  whether it was a promote or rollback, a `PASS`/`FAIL` policy badge, the target
  release, environment, and the reason string.

A **Refresh** button re-fetches all three tables. The Overview also refreshes
automatically after a successful promote or rollback on the Promote page.

---

## Diff page (`/#/diff`)

An interactive form that calls `POST /v1/diff` to compare two releases over a time
window. Inputs:

| Field | Description |
|-------|-------------|
| **Baseline release ID** | The `release_id` of the baseline (older) release |
| **Candidate release ID** | The `release_id` of the release under evaluation |
| **Window** | Time window string: `7d`, `24h`, `30m`, etc. |
| **Environment** | Environment name (default `local`; must match ingested events) |

After clicking **Compute diff**, the page shows:

- **Policy badge** (`PASS`/`FAIL`) and, on failure, the list of constraint reasons.
- **Sample counts** — baseline runs, candidate runs, confidence label (`HIGH`,
  `MEDIUM`, or `LOW`), and an optional reason when confidence is degraded.
- **Metric cards** for cost per run (USD), average latency (ms), and error rate.
  Each card shows baseline (`B`) and candidate (`C`) values plus the delta.
- **Raw diff JSON** in a collapsible panel for debugging.

`POST /v1/diff` is a read-only computation — it does not change promoted pointers or
write to the audit ledger. It does not require the mutation token.

For diff semantics, confidence tiers, and policy evaluation see
[operations-and-policy.md](operations-and-policy.md).

---

## Promote & rollback page (`/#/actions`)

Sends `POST /v1/promote` or `POST /v1/rollback` after confirming a dialog. Inputs:

| Field | Description |
|-------|-------------|
| **Release ID** | The `release_id` to promote or roll back to |
| **Environment** | Environment name (default `local`) |
| **Window** | Time window for evidence sampling (default `7d`) |
| **Reason** (required) | Non-empty reason string recorded in the audit ledger |

Both **Promote** and **Rollback** buttons are disabled while a request is in flight.
The response JSON is shown inline after completion. If the operation is blocked by
policy (HTTP 409), the error message includes the policy constraint reasons.

After a successful mutation, the Overview page refreshes its tables automatically via
`TimelineRefreshContext`.

> **First promotion:** when no prior release has been promoted for a given
> agent/environment, the first promotion always succeeds — policy evaluation is skipped
> and the release is promoted unconditionally.

---

## Authentication in the UI

The server has two access tiers (see [http-api.md](http-api.md) for the full table):

- **Read-only routes** (`GET /v1/*`, `GET /health`, `POST /v1/diff`) — always open on
  loopback; no token required.
- **Mutation routes** (`POST /v1/promote`, `POST /v1/rollback`) — loopback-only by
  default. When `FLIGHTDECK_LOCAL_API_TOKEN` is set on the server, callers must send
  `Authorization: Bearer <token>`.

**When using the static UI served by `flightdeck serve`**, mutations always originate
from `localhost` so they work without a token in the default setup.

If you configure a token (recommended when binding to a non-loopback address), the
static UI cannot inject the token automatically — use the CLI or SDK for mutations in
that configuration, or run the Vite dev server with `VITE_FLIGHTDECK_LOCAL_API_TOKEN`
(see [Development](#development-mode) below).

---

## Development mode

To iterate on the UI source under `web/src/`:

1. Start the API in one terminal from a workspace with `flightdeck.yaml`:

   ```bash
   flightdeck serve                # default 127.0.0.1:8765
   ```

2. In another terminal, run the Vite dev server:

   ```bash
   cd web
   cp .env.example .env.local      # optional: set VITE_FLIGHTDECK_LOCAL_API_TOKEN
   npm ci
   npm run dev                     # http://localhost:5173
   ```

Vite proxies `/v1/*` and `/health` to `http://127.0.0.1:8765` so hot-reload works
against a live FlightDeck server.

After making changes, rebuild the committed static bundle:

```bash
cd web
npm run build
cd ..
git diff --exit-code src/flightdeck/server/static/
```

Commit every file under `src/flightdeck/server/static/` (including the hashed
`assets/*.js` and updated `index.html`). CI enforces this check.

See [web/README.md](../web/README.md) for Playwright E2E test instructions.

---

## Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| **"Loading…" never resolves** | `flightdeck serve` is not running or is on a different port | Start the server; verify `GET http://127.0.0.1:8765/health` returns `{"status": "ok"}` |
| **Tables show empty state** | No releases registered yet | Run `flightdeck release register <path>` and refresh |
| **"Reason is required"** on Promote page | The Reason field is empty | Enter a non-empty reason before clicking Promote or Rollback |
| **HTTP 409 on promote/rollback** | Active policy blocked the action | Check the `policy.reasons` in the error message; adjust the policy or address the constraint |
| **HTTP 401/403 on promote/rollback** | Token mismatch or missing `Authorization` header | Use the CLI or SDK with the correct token, or start the server without `FLIGHTDECK_LOCAL_API_TOKEN` for local dev |
| **Stale data after promote** | Rare race between mutation and auto-refresh | Click **Refresh** on the Overview page manually |
