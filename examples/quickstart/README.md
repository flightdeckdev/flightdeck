# Quickstart examples

These files are meant to be copied or substituted locally:

- `baseline-release/` and `candidate-release/` are example `release.yaml` bundles.
- `pricing-*.yaml` are example pricing tables (immutable by default; use `--replace` to update).
- `policy.yaml` is an example active policy used by `release diff` and `release promote`.
- `*-events.jsonl` contain placeholder `release_id` values (`__BASELINE_RELEASE_ID__`, `__CANDIDATE_RELEASE_ID__`).

Fastest path:

- Run `../../scripts/smoke.sh` from a Unix shell (Git Bash/WSL on Windows).

Manual path:

- See [docs/quickstart.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/quickstart.md).
