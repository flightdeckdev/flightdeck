# Development

## Requirements

- Python **3.11+** (CI runs **3.11** through **3.14** on Ubuntu and Windows)
- Git

## Setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

## Verify

```bash
python -m ruff check src tests
python -m pytest
flightdeck --help
flightdeck doctor
python scripts/quickstart_smoke.py
```

Full command flags and exit codes: [docs/cli.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/cli.md). Cross-platform quickstart parity: **`scripts/quickstart_smoke.py`** (also run in CI).

Before pushing to an **org** remote, follow the maintainer checklist in [docs/github-organization.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/github-organization.md) and [docs/research-workflow.md](https://github.com/flightdeckdev/flightdeck/blob/main/docs/research-workflow.md) ([git remotes](https://github.com/flightdeckdev/flightdeck/blob/main/docs/git-remotes.md): `origin` = personal research, `org` = flightdeckdev).

## Local Demo

```bash
flightdeck init
flightdeck pricing import examples/quickstart/pricing-baseline.yaml
flightdeck pricing import examples/quickstart/pricing-candidate.yaml
flightdeck policy set examples/quickstart/policy.yaml
BASELINE=$(flightdeck release register examples/quickstart/baseline-release)
CANDIDATE=$(flightdeck release register examples/quickstart/candidate-release)

sed "s/__BASELINE_RELEASE_ID__/${BASELINE}/g" examples/quickstart/baseline-events.jsonl > baseline-events.jsonl
sed "s/__CANDIDATE_RELEASE_ID__/${CANDIDATE}/g" examples/quickstart/candidate-events.jsonl > candidate-events.jsonl

flightdeck runs ingest baseline-events.jsonl
flightdeck runs ingest candidate-events.jsonl

flightdeck release diff "$BASELINE" "$CANDIDATE" --window 7d
flightdeck release promote "$BASELINE" --env local --window 7d --reason "initial baseline"
flightdeck release history --agent agent_support --env local
```

For a fully runnable demo that generates matching run events after release registration:

```bash
./scripts/smoke.sh
```

## Local State

`flightdeck init` creates `flightdeck.yaml`. By default, local SQLite data lives at:

```text
.flightdeck/flightdeck.db
```

## Troubleshooting

If your OS temp directory is restricted, set `TMPDIR`, `TEMP`, or `TMP` to a repo-local `.tmp`
directory before running tests.

On some Windows setups, pytest may fail to create or clean its temp directories under the default
`%TEMP%` path. If you see `PermissionError` errors mentioning `pytest-of-...` or `pytest`, point temp
dirs at the repo-local `.tmp/` directory:

```powershell
$env:TEMP = (Resolve-Path .tmp).Path
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
.\.venv\Scripts\python.exe -m pytest
```

By default, `tests/conftest.py` also redirects `TEMP`/`TMP` into `.tmp/` during pytest on Windows. Set
`FLIGHTDECK_USE_SYSTEM_TEMP=1` if you want to force pytest to use your normal OS temp directory instead.

If your shell does not activate virtual environments in the same way as the examples, use the
virtual environment's Python executable directly:

```bash
.venv/bin/python -m pytest
```
