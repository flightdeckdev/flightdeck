# CI / GitOps examples

These files show a **register → ingest → diff (policy gate) → verify** loop you can drop into a pipeline. They mirror `examples/quickstart` and the `flightdeck-quickstart-verify` script, but stop **before** promotion so a pull request can fail when the active policy would reject the candidate.

## Policy gate exit code

`flightdeck release diff` accepts **`--fail-on-policy`**: after printing the diff, the command exits **1** when the active policy does not pass (same semantics as a failed `release promote`, without writing the ledger).

Use this flag in CI so a red build means “unsafe to ship under current policy,” not only “CLI error.”

## `ledger-gate.sh` (bash)

Environment:

| Variable | Required | Meaning |
|----------|----------|---------|
| `WORKSPACE` | yes | **Dedicated throwaway directory** for `flightdeck.yaml` and the SQLite DB (the script **deletes and recreates** it each run so CI reruns stay deterministic) |
| `QUICKSTART_ROOT` | yes | Path to `examples/quickstart` (or your own copy of those fixtures) |
| `FD_PROJECT` | no | If set, invokes `uv run --directory "$FD_PROJECT" flightdeck …` from `WORKSPACE` (FlightDeck monorepo / dev clone). If unset, uses `flightdeck` on `PATH` (for example after `pip install flightdeck-ai`). |

Example (monorepo / local clone with **uv**):

```bash
export FD_PROJECT=/path/to/flightdeck
export WORKSPACE="$(mktemp -d)"
export QUICKSTART_ROOT="$FD_PROJECT/examples/quickstart"
bash "$FD_PROJECT/examples/ci/ledger-gate.sh"
```

Example (**PyPI** install, fixtures from a checkout of this repo):

```bash
python -m venv .venv && . .venv/bin/activate
pip install "flightdeck-ai>=1.0.2"
export WORKSPACE="$(mktemp -d)"
export QUICKSTART_ROOT=/path/to/flightdeck/examples/quickstart
bash /path/to/flightdeck/examples/ci/ledger-gate.sh
```

## GitHub Actions

Copy a workflow from `github-actions/` into `.github/workflows/` in your repository and adjust paths, Python version, and FlightDeck version pins.

| File | Use when |
|------|----------|
| [`policy-gate-monorepo.yml`](github-actions/policy-gate-monorepo.yml) | This repository (or a fork): `uv sync` + `ledger-gate.sh` with `FD_PROJECT` pointing at the checkout. |
| [`policy-gate-pypi.yml`](github-actions/policy-gate-pypi.yml) | Another repo: install **`flightdeck-ai`** from PyPI and sparse-checkout upstream `examples/quickstart` for fixtures (pin the checkout ref to match your installed version when possible). |

### Promoting from CI

`flightdeck release promote` is intentionally **not** in the gate script: many teams run diff/verify on every PR and only promote from a protected branch or manual workflow with secrets and review. If you automate promote, reuse the same workspace (or a trusted replica), set policy explicitly, and pass a non-empty `--reason` (for example the Git run URL).

## Related

- [Quickstart fixtures](../quickstart/README.md)
- [Deploy `flightdeck serve`](../deploy/README.md)
- [Runtime event emitter](../integration/README.md)
- [CLI reference](../../docs/cli.md)
- [Operations and policy](../../docs/operations-and-policy.md)
