# Security

## Supported Versions

From **v1.0.0**, security fixes land on **`main`** and should be released as **patch** versions on
the latest **1.x** line when applicable. Report against a specific **version** or **commit**.

## Reporting A Vulnerability

Do not open a public issue for suspected vulnerabilities.

On **[github.com/flightdeckdev/flightdeck](https://github.com/flightdeckdev/flightdeck)**, prefer **GitHub → Security → Report a vulnerability** once **private vulnerability reporting** is enabled for that repository.

If private reporting is unavailable, contact the maintainer privately through the **[repository owner profile](https://github.com/flightdeckdev)** (organization) or your fork’s owner—do not use public issues for suspected vulnerabilities.

Please include:

- affected version or commit
- reproduction steps
- impact
- suggested remediation, if known

## Secrets

Do not include credentials, API keys, customer data, traces with sensitive content, or private
company information in issues, discussions, examples, or tests.

### Repository hygiene

- **Local ledger:** default SQLite path lives under **`.flightdeck/`**; that directory is **gitignored**. Do not force-add it.
- **Environment:** never commit **`.env`** or **`.env.*`** files.
- **Optional local-only trees:** **`private/`** and **`secrets/`** are gitignored for material that must not ship with the public tree.
- **Keys / certs:** patterns such as **`*.pem`**, **`*.p12`**, and common `*credentials*.json` names are ignored—still review `git status` before every commit.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for a pre-push checklist aligned with the **[flightdeckdev](https://github.com/flightdeckdev)** org.

## Local HTTP API (`flightdeck serve`)

### `FLIGHTDECK_LOCAL_API_TOKEN` — what it is (and is not)

- **You choose the value.** FlightDeck does **not** generate, mint, or rotate this string for you. It is a **shared secret** you set in the server environment (same idea as a static API key). A typical choice is a long random value (for example `openssl rand -hex 32` as in **[docs/http-api.md](docs/http-api.md)**).
- **What it gates:** access to this process’s **HTTP JSON API** (`GET /v1/*` when set, plus ledger writes and ingest) via the **`Authorization: Bearer …`** header. SDKs use **`api_token=`**; scripts and agents send the header explicitly; the **bundled React UI** uses **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** at build time (or **`web/.env.local`** under `npm run dev`) so the browser can send the **same** secret — see **[docs/web-ui.md](docs/web-ui.md)**.
- **What it is not:** end-user login, OAuth/OIDC, SSO, or per-person identity inside FlightDeck. Those are **not** part of today’s core product; the roadmap treats stronger identity as a longer arc (see **[ROADMAP.md](ROADMAP.md)**).

The bundled server is intended for **local development and demos**. **`POST /v1/promote`**, **`POST /v1/promote/request`**, **`POST /v1/promote/confirm`**, **`POST /v1/rollback`**, and **`POST /v1/events`** (run event ingest) share one **ledger-write** access model in server code: with no token configured, only **loopback** clients (`127.0.0.1`, `::1`, `localhost`, and the Starlette test client) may call them. If you set **`FLIGHTDECK_LOCAL_API_TOKEN`**, every such request must include **`Authorization: Bearer <that value>`**; use a strong random value and treat it like a local secret. Remote emitters (agents, sidecars) must use the Bearer path when the server listens beyond loopback.

**Human approval** (`promotion_requires_approval: true` in `flightdeck.yaml`) adds a **second actor step** before a promote is applied: **`POST /v1/promote/request`** creates a pending row; **`POST /v1/promote/confirm`** completes it. **Policy still runs on confirm** — approval is not a bypass; a request that fails policy remains blocked with the same HTTP **409** outcome as a direct promote.

When **`FLIGHTDECK_LOCAL_API_TOKEN`** is set, **read-only `GET /v1/*`** routes (workspace, metrics, runs, audit slices, etc.) require the **same** **`Authorization: Bearer`** header as ledger writes, so port-forwards and shared networks do not expose the audit trail without credentials. With no token configured, those reads stay open—use network controls if you bind beyond loopback.

**`POST /v1/diff`** is intentionally unauthenticated (read-only computation on stored evidence). When `flightdeck serve` binds to `127.0.0.1` (the default), callers are constrained by network topology; if you use **`--host 0.0.0.0`**, treat **`POST /v1/diff`** exposure explicitly.

### Identity passthrough headers — when to trust them

Mutating routes accept two HTTP headers — **`X-FlightDeck-Actor`** and **`X-Forwarded-User`** — and prefer them over the body `actor` field when stamping the audit ledger (precedence and exact semantics: **[docs/http-api.md](docs/http-api.md#identity-passthrough-audit-actor)**). This unlocks SSO-stamped audit rows behind an existing auth layer (oauth2-proxy, Pomerium, Authelia, Cloudflare Access, nginx `auth_request`) **without** FlightDeck owning identity.

**Threat model:** both headers are **trivially forgeable** by any client that can reach the FlightDeck process directly. They are safe to trust **only** when:

1. **All inbound traffic flows through a trusted reverse proxy** (no path that bypasses it — no `--host 0.0.0.0` shortcut, no port-forward, no co-located client).
2. **That proxy strips any incoming `X-Forwarded-User` and `X-FlightDeck-Actor` headers from client requests** before injecting its own authenticated value. Stripping is the single most important step; without it, a client can spoof the identity by setting the header themselves. Examples:
   - **nginx:** `proxy_set_header X-Forwarded-User $remote_user;` after upstream auth.
   - **Caddy:** `header_up X-Forwarded-User {http.auth.user.id}` with the relevant `forward_auth` handler.
   - **oauth2-proxy:** sets `X-Forwarded-User` after a successful OIDC handshake; ensure the upstream is bound to loopback so direct ingress is impossible.
3. **The Bearer token (`FLIGHTDECK_LOCAL_API_TOKEN`) is also set** so a leaked / mis-routed request cannot reach mutating routes without it.

Without those three controls, treat the headers as advisory only and rely on the body `actor` plus the Bearer-gate for audit attribution. A future release will add scoped tokens with an embedded identity claim so callers can self-attest without depending on a proxy layer.

### Outbound webhooks — SSRF defence

`POST /v1/webhooks` registers a URL that receives every promote / rollback / policy-blocked payload. The server validates the URL on create and **rejects**:

- schemes other than **`http`** or **`https`** (no `file://`, `gopher://`, `ftp://`, `javascript:`, `data:`)
- link-local IP literals (covers AWS IMDS `169.254.169.254`, ECS `169.254.170.2`, and IPv6 `fe80::/10`)
- known cloud-metadata hostnames (`metadata.google.internal`, `metadata`, `instance-data`, `instance-data.ec2.internal`)

Loopback and RFC1918 private addresses are intentionally **allowed** — FlightDeck is local-first, and self-hosted Slack / Discord receivers commonly live on private networks. Use HTTPS in production; HTTP is permitted for local relays and testing.

Webhook payloads carry **promote / rollback metadata** including the actor, reason, environment, and release id. Treat any registered webhook URL as receiving the same audit-grade information the ledger holds.

**SQLite:** one hot writer per workspace file is the safe default; parallel servers on the same path risk **`database is locked`**. The server retries for a bounded time (see **`flightdeck serve --help`** and **`docs/http-api.md`**). Prefer **separate workspace directories** per concurrent process in CI, or **`database_url`** (PostgreSQL) for multi-writer deployments.

For **Compose healthchecks**, **SQLite backup** scheduling, and an **operator checklist** (logs, restarts, one writer per workspace file), see **[examples/deploy/README.md](examples/deploy/README.md)**.
