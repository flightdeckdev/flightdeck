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

The bundled server is intended for **local development and demos**. **`POST /v1/promote`**, **`POST /v1/promote/request`**, **`POST /v1/promote/confirm`**, **`POST /v1/rollback`**, and **`POST /v1/events`** (run event ingest) share one **ledger-write** access model in server code: with no token configured, only **loopback** clients (`127.0.0.1`, `::1`, `localhost`, and the Starlette test client) may call them. If you set **`FLIGHTDECK_LOCAL_API_TOKEN`**, every such request must include **`Authorization: Bearer <that value>`**; use a strong random value and treat it like a local secret. Remote emitters (agents, sidecars) must use the Bearer path when the server listens beyond loopback.

**Human approval** (`promotion_requires_approval: true` in `flightdeck.yaml`) adds a **second actor step** before a promote is applied: **`POST /v1/promote/request`** creates a pending row; **`POST /v1/promote/confirm`** completes it. **Policy still runs on confirm** — approval is not a bypass; a request that fails policy remains blocked with the same HTTP **409** outcome as a direct promote.

When **`FLIGHTDECK_LOCAL_API_TOKEN`** is set, **read-only `GET /v1/*`** routes (workspace, metrics, runs, audit slices, etc.) require the **same** **`Authorization: Bearer`** header as ledger writes, so port-forwards and shared networks do not expose the audit trail without credentials. With no token configured, those reads stay open—use network controls if you bind beyond loopback.

**`POST /v1/diff`** is intentionally unauthenticated (read-only computation on stored evidence). When `flightdeck serve` binds to `127.0.0.1` (the default), callers are constrained by network topology; if you use **`--host 0.0.0.0`**, treat **`POST /v1/diff`** exposure explicitly.

**SQLite:** one hot writer per workspace file is the safe default; parallel servers on the same path risk **`database is locked`**. The server retries for a bounded time (see **`flightdeck serve --help`** and **`docs/http-api.md`**). Prefer **separate workspace directories** per concurrent process in CI, or **`database_url`** (PostgreSQL) for multi-writer deployments.

For **Compose healthchecks**, **SQLite backup** scheduling, and an **operator checklist** (logs, restarts, one writer per workspace file), see **[examples/deploy/README.md](examples/deploy/README.md)**.
