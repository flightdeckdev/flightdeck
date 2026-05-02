"""Cross-platform CI ledger gate (register → ingest → diff --fail-on-policy → verify).

Runs the FlightDeck CLI via ``sys.executable -m flightdeck.cli.main`` so CI does not rely on
bash, CRLF-safe shebangs, or ``uv run`` spawning a second resolver (which can fail on Windows
file locks). Same behavior as ledger-gate.sh.

Env (required):
  WORKSPACE        — empty dir path for flightdeck.yaml + SQLite (wiped on each run)
  QUICKSTART_ROOT  — path to examples/quickstart (or equivalent fixtures)

Env (optional, unused but kept for workflow compatibility):
  FD_PROJECT       — ignored; the active interpreter must already have ``flightdeck`` installed
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_REL_ID = re.compile(r"rel_[0-9a-f]{12}")


def _die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _fd_args(args: list[str]) -> list[str]:
    return [sys.executable, "-m", "flightdeck.cli.main", *args]


def _run(
    workspace: Path,
    args: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(
        _fd_args(args),
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and p.returncode != 0:
        detail = (p.stderr or p.stdout or "").strip()
        _die(f"flightdeck {' '.join(args)} failed (exit {p.returncode}):\n{detail}")
    return p


def _register_id(workspace: Path, bundle: Path) -> str:
    p = _run(workspace, ["release", "register", str(bundle)])
    matches = _REL_ID.findall(p.stdout)
    if not matches:
        _die(f"no release_id in register stdout: {p.stdout!r}")
    return matches[-1]


def main() -> None:
    try:
        ws_raw = os.environ["WORKSPACE"]
        qs_raw = os.environ["QUICKSTART_ROOT"]
    except KeyError as exc:
        _die(f"missing required environment variable: {exc}")

    ws_norm = ws_raw.strip()
    if ws_norm in ("/", ".", ".."):
        _die(f"refusing unsafe WORKSPACE={ws_raw!r}")

    workspace = Path(ws_raw)
    quickstart = Path(qs_raw)

    if not quickstart.is_dir():
        _die(f"QUICKSTART_ROOT is not a directory: {quickstart}")

    gh_ws = os.environ.get("GITHUB_WORKSPACE", "").strip()
    if gh_ws and workspace.resolve() == Path(gh_ws).resolve():
        _die("WORKSPACE must not be the same path as GITHUB_WORKSPACE")

    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    _run(workspace, ["init"])
    _run(workspace, ["pricing", "import", str(quickstart / "pricing-baseline.yaml")])
    _run(workspace, ["pricing", "import", str(quickstart / "pricing-candidate.yaml")])
    policy_path = Path(__file__).resolve().parent / "ledger-gate-policy.yaml"
    _run(workspace, ["policy", "set", str(policy_path)])

    baseline_id = _register_id(workspace, quickstart / "baseline-release")
    candidate_id = _register_id(workspace, quickstart / "candidate-release")

    baseline_ph = "__BASELINE_RELEASE_ID__"
    candidate_ph = "__CANDIDATE_RELEASE_ID__"
    be = (quickstart / "baseline-events.jsonl").read_text(encoding="utf-8").replace(
        baseline_ph, baseline_id
    )
    ce = (quickstart / "candidate-events.jsonl").read_text(encoding="utf-8").replace(
        candidate_ph, candidate_id
    )
    baseline_events = workspace / "baseline-events.jsonl"
    candidate_events = workspace / "candidate-events.jsonl"
    baseline_events.write_text(be, encoding="utf-8", newline="\n")
    candidate_events.write_text(ce, encoding="utf-8", newline="\n")

    _run(workspace, ["runs", "ingest", str(baseline_events)])
    _run(workspace, ["runs", "ingest", str(candidate_events)])
    _run(
        workspace,
        [
            "release",
            "diff",
            baseline_id,
            candidate_id,
            "--window",
            "7d",
            "--fail-on-policy",
        ],
    )
    _run(
        workspace,
        ["release", "verify", baseline_id, "--path", str(quickstart / "baseline-release")],
    )
    _run(
        workspace,
        ["release", "verify", candidate_id, "--path", str(quickstart / "candidate-release")],
    )
    _run(workspace, ["doctor"])
    print("ledger-gate: OK")


if __name__ == "__main__":
    main()
