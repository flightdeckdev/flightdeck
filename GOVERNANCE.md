# Governance

This document describes how decisions are made in the FlightDeck project, who can make them, and how the project plans to evolve its governance over time.

For the day-to-day engineering doctrine (mission, non-goals, public contracts, product doctrine, verification, doc rules), see [`AGENTS.md`](AGENTS.md). This file complements it; it does not override it.

## Project model

FlightDeck is currently a **single-maintainer project**. The maintainer is:

- **Gottam Sai Bharath** ([@Gsbreddy](https://github.com/Gsbreddy))

The project follows a *benevolent dictator* model: the maintainer has final say on all merges, releases, roadmap direction, and infrastructure choices. This is an honest reflection of the project's stage, not an aspiration. Concentrating decision authority lets a young project move quickly and stay coherent; the next section describes how that responsibility is meant to dissolve as the project grows.

## Decision-making

- **Day-to-day decisions** (bug fixes, doc tweaks, minor refactors, new tests, dependency bumps) are made by the maintainer at merge time.
- **Non-trivial changes** — anything that adds, removes, or alters a public contract (CLI synopsis or exit codes, `release.yaml` shape, `RunEvent` schema, HTTP `/v1/*` routes, policy YAML shape, audit ledger semantics) — must be proposed first in an **issue or draft PR**. The proposal must explain which doctrine items in [`AGENTS.md`](AGENTS.md) it strengthens (release artifact integrity, runtime evidence, safety ledger accuracy, policy-gated promotion, audit history, or developer onboarding). Changes that do not strengthen at least one of those items wait.
- **Out-of-scope changes** match the **Non-goals** list in [`AGENTS.md`](AGENTS.md). Re-opening any of those (prompt IDEs, in-product agent orchestration frameworks, dashboards before CLI is proven, default gateway/proxy, compliance-scanner product, fine-tuning ops, broad plugin systems) requires a written argument with concrete user evidence and explicit acknowledgement of the trust-boundary cost.

## Public contracts

The list of public contracts and the stability bar for each is the **Public contracts** section of [`AGENTS.md`](AGENTS.md). Any change to a public contract is a release-notes-worthy event and must be reflected in [`RELEASE_NOTES.md`](RELEASE_NOTES.md) and [`CHANGELOG.md`](CHANGELOG.md).

## Releases

- The project follows [Semantic Versioning](https://semver.org/) from **v1.0.0** onward.
- **Patch and minor** releases ship on a rolling basis whenever there is meaningful, tested work to ship.
- **Major** releases require an explicit signal in [`ROADMAP.md`](ROADMAP.md) plus a corresponding [`RELEASE_NOTES.md`](RELEASE_NOTES.md) entry describing the breaking change and any migration steps.
- Release publication is automated via [`.github/workflows/release-pypi.yml`](.github/workflows/release-pypi.yml) and tag pushes; see [`VERSIONING.md`](VERSIONING.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

Vulnerabilities must be reported privately per [`SECURITY.md`](SECURITY.md), not in public issues or pull requests. The maintainer will acknowledge reports within five business days and aim to ship a fix within the timelines in that document.

## Code of Conduct

All participation in FlightDeck spaces is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Enforcement is handled by the maintainer; reports go to the contact listed in that file.

## Becoming a maintainer

Maintainership is by **invitation**, not by request. Signals that increase the likelihood of an invitation:

- A sustained track record (months, not weeks) of high-quality contributions across code, tests, and documentation
- Demonstrated alignment with the doctrine in [`AGENTS.md`](AGENTS.md), especially the non-goals and the product-doctrine list
- Sound review judgment on others' pull requests, including the ability to say "this waits"
- Reliability: responsive to review, finishes what they start, communicates blockers early

There is no fixed number of maintainers, and no required cadence of contribution to remain one. A maintainer who is inactive for an extended period and unreachable will be moved to an emeritus role.

## Path to broader governance

The single-maintainer model is a starting state, not the goal. The project will transition to a small **steering committee** when *all* of the following are true:

- At least **three active maintainers** hold merge rights and have demonstrated independent judgment on non-trivial changes
- No single contributor is responsible for more than **70%** of merged commits over the prior 6 months
- A short **trademark policy** is published (clarifying use of the "FlightDeck" name and marks)
- A **contribution license model** is documented (today the implicit model is the Apache-2.0 inbound = outbound; the project may add a DCO or CLA at that time)

At that point this file will be amended to describe how the steering committee makes decisions, how disputes are escalated, and how new committee members are added or rotated off.

## License and contributions

The project is licensed under the **Apache License, Version 2.0** (see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE)). Contributions are accepted under the same license (inbound = outbound).

**DCO sign-off** (`git commit -s`) is welcomed but **not currently required**. The maintainer may make sign-off mandatory as part of the steering-committee transition above; if that happens, it will be announced in [`CONTRIBUTING.md`](CONTRIBUTING.md) with a grace period.

---

_If you want to discuss governance proposals, open an issue with the label `governance` or start a thread in [GitHub Discussions](https://github.com/flightdeckdev/flightdeck/discussions)._
