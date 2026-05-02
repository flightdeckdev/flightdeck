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

The bundled server is intended for **local development and demos**. **`POST /v1/promote`** and **`POST /v1/rollback`** are gated so that, with no token configured, only **loopback** clients can invoke them. If you set **`FLIGHTDECK_LOCAL_API_TOKEN`**, every mutation request must include **`Authorization: Bearer <that value>`**; use a strong random value and treat it like a local secret. Do not expose **`flightdeck serve`** on untrusted networks without understanding that **`POST /v1/events`** and **`POST /v1/diff`** are not behind the same Bearer gate (ingest and diff are still local-trust assumptions).
