"""Shared quickstart demo / CI verification (fixtures + subprocess CLI calls)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_PH = "__BASELINE_RELEASE_ID__"
CANDIDATE_PH = "__CANDIDATE_RELEASE_ID__"


def flightdeck_argv() -> list[str]:
    exe = shutil.which("flightdeck")
    if exe:
        return [exe]
    return [sys.executable, "-m", "flightdeck.cli.main"]


def quickstart_root(*, env_dir: str | None = None) -> Path:
    """Resolve the directory containing quickstart YAML/JSONL fixtures.

    Order: explicit ``env_dir``, ``FLIGHTDECK_QUICKSTART_ROOT``, repo
    ``examples/quickstart``, then wheel-bundled ``_bundled_quickstart``.
    """
    if env_dir:
        p = Path(env_dir).expanduser()
        if not p.is_dir():
            msg = f"Not a directory: {p}"
            raise FileNotFoundError(msg)
        return p.resolve()

    env = os.environ.get("FLIGHTDECK_QUICKSTART_ROOT")
    if env:
        p = Path(env).expanduser()
        if not p.is_dir():
            msg = (
                f"FLIGHTDECK_QUICKSTART_ROOT is not a directory: {p}. "
                "Unset it or point it at examples/quickstart."
            )
            raise FileNotFoundError(msg)
        return p.resolve()

    repo = Path(__file__).resolve().parents[2]
    examples = repo / "examples" / "quickstart"
    if examples.is_dir():
        return examples

    bundled = Path(__file__).resolve().parent / "_bundled_quickstart"
    if bundled.is_dir() and (bundled / "policy.yaml").is_file():
        return bundled

    msg = (
        "Quickstart fixtures not found. Clone the repo or set FLIGHTDECK_QUICKSTART_ROOT "
        "to a copy of examples/quickstart."
    )
    raise FileNotFoundError(msg)


def _run(fd: list[str], *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*fd, *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def run_quickstart_verify(
    workspace: Path,
    qs: Path,
    fd: list[str] | None = None,
    *,
    verify: bool = True,
    doctor: bool = True,
    promote_reason: str = "quickstart smoke",
) -> None:
    """Run the full quickstart workflow used by CI (temp workspace must exist)."""
    fd = fd or flightdeck_argv()
    baseline_events = workspace / "baseline-events.jsonl"
    candidate_events = workspace / "candidate-events.jsonl"

    _run(fd, "init", cwd=workspace)
    _run(fd, "pricing", "import", str(qs / "pricing-baseline.yaml"), cwd=workspace)
    _run(fd, "pricing", "import", str(qs / "pricing-candidate.yaml"), cwd=workspace)
    _run(fd, "policy", "set", str(qs / "policy.yaml"), cwd=workspace)

    reg_b = _run(fd, "release", "register", str(qs / "baseline-release"), cwd=workspace)
    baseline_id = reg_b.stdout.strip()
    reg_c = _run(fd, "release", "register", str(qs / "candidate-release"), cwd=workspace)
    candidate_id = reg_c.stdout.strip()

    baseline_events.write_text(
        (qs / "baseline-events.jsonl").read_text(encoding="utf-8").replace(BASELINE_PH, baseline_id),
        encoding="utf-8",
    )
    candidate_events.write_text(
        (qs / "candidate-events.jsonl").read_text(encoding="utf-8").replace(CANDIDATE_PH, candidate_id),
        encoding="utf-8",
    )

    _run(fd, "runs", "ingest", str(baseline_events), cwd=workspace)
    _run(fd, "runs", "ingest", str(candidate_events), cwd=workspace)
    _run(fd, "release", "diff", baseline_id, candidate_id, "--window", "7d", cwd=workspace)
    _run(
        fd,
        "release",
        "promote",
        baseline_id,
        "--env",
        "local",
        "--window",
        "7d",
        "--reason",
        promote_reason,
        cwd=workspace,
    )
    _run(fd, "release", "history", "--agent", "agent_support", "--env", "local", cwd=workspace)
    if verify:
        _run(fd, "release", "verify", baseline_id, "--path", str(qs / "baseline-release"), cwd=workspace)
    if doctor:
        _run(fd, "doctor", cwd=workspace)


def run_demo_happy_path(
    workspace: Path,
    qs: Path,
    fd: list[str] | None = None,
    *,
    verify: bool = False,
    doctor: bool = False,
    promote_reason: str = "demo",
) -> None:
    """Minimal demo: same ledger steps as CI verify, optional verify/doctor."""
    run_quickstart_verify(
        workspace,
        qs,
        fd,
        verify=verify,
        doctor=doctor,
        promote_reason=promote_reason,
    )


def demo_session(
    *,
    verify: bool,
    doctor: bool,
    qs_dir: str | None,
    promote_reason: str,
    keep_workspace: bool,
) -> Path | None:
    """Create a temp workspace, run the demo.

    Removes the workspace when ``keep_workspace`` is false (unless setup fails).
    Returns the workspace path when ``keep_workspace`` is true; otherwise ``None``.
    """
    qs = quickstart_root(env_dir=qs_dir)
    fd = flightdeck_argv()
    tmp_s = tempfile.mkdtemp(prefix="flightdeck_demo_")
    workspace = Path(tmp_s)
    try:
        run_demo_happy_path(
            workspace,
            qs,
            fd,
            verify=verify,
            doctor=doctor,
            promote_reason=promote_reason,
        )
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
    if keep_workspace:
        return workspace
    shutil.rmtree(workspace, ignore_errors=True)
    return None
