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

The bundled server is intended for **local development and demos**. **`POST /v1/promote`**, **`POST /v1/promote/request`**, **`POST /v1/promote/confirm`**, and **`POST /v1/rollback`** are gated in server code so that, with no token configured, only **loopback** clients (`127.0.0.1`, `::1`, `localhost`) can invoke them. If you set **`FLIGHTDECK_LOCAL_API_TOKEN`**, every mutation request must include **`Authorization: Bearer <that value>`**; use a strong random value and treat it like a local secret.

**Human approval** (`promotion_requires_approval: true` in `flightdeck.yaml`) adds a **second actor step** before a promote is applied: **`POST /v1/promote/request`** creates a pending row; **`POST /v1/promote/confirm`** completes it. **Policy still runs on confirm** — approval is not a bypass; a request that fails policy remains blocked with the same HTTP **409** outcome as a direct promote. **`GET /v1/workspace`**, **`GET /v1/promotion-requests`**, and other read-only **`GET /v1/*`** routes stay on the read tier (no Bearer required unless you add external controls).

**`POST /v1/events`** and **`POST /v1/diff`** have **no server-side host or token check** in `server/routes/ingest.py` and `server/routes/actions.py`. They are open to any caller that can reach the server. When `flightdeck serve` binds to `127.0.0.1` (the default), this is safe by network topology. If you use `--host 0.0.0.0` or bind to a non-loopback address, event ingest and diff become reachable from any client. Protect them at the network layer (firewall / reverse proxy) if the server is exposed on a shared or public network.

For **Compose healthchecks**, **SQLite backup** scheduling, and an **operator checklist** (logs, restarts, one writer per workspace file), see **[examples/deploy/README.md](examples/deploy/README.md)**.
