# CI / GitOps examples

These files show a **register → ingest → diff (policy gate) → verify** loop you can drop into a pipeline. They mirror `examples/quickstart` and the `flightdeck-quickstart-verify` script, but stop **before** promotion so a pull request can fail when the active policy would reject the candidate.

## Policy gate exit code

`flightdeck release diff` accepts **`--fail-on-policy`**: after printing the diff, the command exits **1** when the active policy does not pass (same semantics as a failed `release promote`, without writing the ledger).

Use this flag in CI so a red build means “unsafe to ship under current policy,” not only “CLI error.”

## `ledger_gate.py` (recommended)

Canonical cross-platform gate (used by **`.github/workflows/ci.yml`**). Runs the CLI as
`python -m flightdeck.cli.main` from the **same interpreter** that executes the script (the
`uv` devenv on CI, or `python` after `pip install flightdeck-ai`).

Environment:

| Variable | Required | Meaning |
|----------|----------|---------|
| `WORKSPACE` | yes | **Dedicated throwaway directory** for `flightdeck.yaml` + SQLite (**deleted and recreated** each run) |
| `QUICKSTART_ROOT` | yes | Path to `examples/quickstart` (or your own copy of those fixtures) |
| `FD_PROJECT` | — | **Ignored** by `ledger_gate.py` (kept on env in workflows for documentation only). |

Policy for the diff step is **`ledger-gate-policy.yaml`** next to this README (not `quickstart/policy.yaml`): quickstart candidate cost is **~\$5/run** while quickstart policy caps **\$4**, so `--fail-on-policy` would fail there by design.

`ledger-gate.sh` is a thin **`exec …/ledger_gate.py`** wrapper for local bash users.

Example (monorepo with **uv**):

```bash
export WORKSPACE="$(mktemp -d)"
export QUICKSTART_ROOT="$PWD/examples/quickstart"
uv run python examples/ci/ledger_gate.py
```

Example (**PyPI** install):

```bash
pip install "flightdeck-ai>=1.0.4"
export WORKSPACE="$(mktemp -d)"
export QUICKSTART_ROOT=/path/to/flightdeck/examples/quickstart
python /path/to/flightdeck/examples/ci/ledger_gate.py
```

## GitHub Actions

Copy a workflow from `github-actions/` into `.github/workflows/` in your repository and adjust paths, Python version, and FlightDeck version pins.

| File | Use when |
|------|----------|
| [`policy-gate-monorepo.yml`](github-actions/policy-gate-monorepo.yml) | This repository (or a fork): `uv sync` + `uv run python examples/ci/ledger_gate.py`. |
| [`policy-gate-pypi.yml`](github-actions/policy-gate-pypi.yml) | Another repo: install **`flightdeck-ai`** from PyPI and sparse-checkout upstream `examples/quickstart` for fixtures (pin the checkout ref to match your installed version when possible). |

### Promoting from CI

`flightdeck release promote` is intentionally **not** in the gate script: many teams run diff/verify on every PR and only promote from a protected branch or manual workflow with secrets and review. If you automate promote, reuse the same workspace (or a trusted replica), set policy explicitly, and pass a non-empty `--reason` (for example the Git run URL).

## Related

- [Quickstart fixtures](../quickstart/README.md)
- [Deploy `flightdeck serve`](../deploy/README.md)
- [Runtime event emitter](../integration/README.md)
- [CLI reference](../../docs/cli.md)
- [Operations and policy](../../docs/operations-and-policy.md)
