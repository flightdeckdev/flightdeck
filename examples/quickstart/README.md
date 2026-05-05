# Quickstart examples

These files are meant to be copied or substituted locally:

- `baseline-release/` and `candidate-release/` are example `release.yaml` bundles.
- `pricing-*.yaml` are example pricing tables (immutable by default; use `--replace` to update).
- `policy.yaml` is an example active policy used by `release diff` and `release promote`.
- `*-events.jsonl` contain placeholder `release_id` values (`__BASELINE_RELEASE_ID__`, `__CANDIDATE_RELEASE_ID__`).

Fastest path after **`pip install flightdeck-ai`**:

```bash
flightdeck demo
```

Full CI parity (verify + doctor; from **repository root** with **uv**):

```bash
uv run flightdeck-quickstart-verify
```

Or **`python -m flightdeck.quickstart_smoke`** / **`py -3 -m flightdeck.quickstart_smoke`** in an activated venv. Unix shell alternative from this directory: **`../../scripts/smoke.sh`** (Git Bash / WSL on Windows).

Manual step-by-step: root **[README.md](../../README.md)**.

CI / GitOps: **[../ci/README.md](../ci/README.md)** (policy gate script and GitHub Actions templates).

Deploy **`serve`**: **[../deploy/README.md](../deploy/README.md)**. Runtime **`POST /v1/events`**: **[../integration/README.md](../integration/README.md)**.
