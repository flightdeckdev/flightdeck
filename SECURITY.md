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

See **[docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md)** for a pre-push checklist aligned with the **[flightdeckdev](https://github.com/flightdeckdev)** org.
