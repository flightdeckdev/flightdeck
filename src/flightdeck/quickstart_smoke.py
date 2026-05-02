"""Cross-platform quickstart smoke: mirrors ``examples/quickstart`` in a temp workspace."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QS = REPO / "examples" / "quickstart"
BASELINE_PH = "__BASELINE_RELEASE_ID__"
CANDIDATE_PH = "__CANDIDATE_RELEASE_ID__"


def _flightdeck_cmd() -> list[str]:
    exe = shutil.which("flightdeck")
    if exe:
        return [exe]
    return [sys.executable, "-m", "flightdeck.cli.main"]


def _run(fd: list[str], *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*fd, *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def main() -> None:
    fd = _flightdeck_cmd()
    with tempfile.TemporaryDirectory(prefix="fd_qs_", ignore_cleanup_errors=True) as tmp_s:
        tmp = Path(tmp_s)
        baseline_events = tmp / "baseline-events.jsonl"
        candidate_events = tmp / "candidate-events.jsonl"

        _run(fd, "init", cwd=tmp)
        _run(fd, "pricing", "import", str(QS / "pricing-baseline.yaml"), cwd=tmp)
        _run(fd, "pricing", "import", str(QS / "pricing-candidate.yaml"), cwd=tmp)
        _run(fd, "policy", "set", str(QS / "policy.yaml"), cwd=tmp)

        reg_b = _run(fd, "release", "register", str(QS / "baseline-release"), cwd=tmp)
        baseline_id = reg_b.stdout.strip()
        reg_c = _run(fd, "release", "register", str(QS / "candidate-release"), cwd=tmp)
        candidate_id = reg_c.stdout.strip()

        baseline_events.write_text(
            (QS / "baseline-events.jsonl").read_text(encoding="utf-8").replace(BASELINE_PH, baseline_id),
            encoding="utf-8",
        )
        candidate_events.write_text(
            (QS / "candidate-events.jsonl").read_text(encoding="utf-8").replace(CANDIDATE_PH, candidate_id),
            encoding="utf-8",
        )

        _run(fd, "runs", "ingest", str(baseline_events), cwd=tmp)
        _run(fd, "runs", "ingest", str(candidate_events), cwd=tmp)
        _run(fd, "release", "diff", baseline_id, candidate_id, "--window", "7d", cwd=tmp)
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
            "quickstart smoke",
            cwd=tmp,
        )
        _run(fd, "release", "history", "--agent", "agent_support", "--env", "local", cwd=tmp)
        _run(fd, "release", "verify", baseline_id, "--path", str(QS / "baseline-release"), cwd=tmp)
        _run(fd, "doctor", cwd=tmp)

    print("quickstart_smoke: OK")


def quickstart_verify_main() -> None:
    """Entry point for ``flightdeck-quickstart-verify`` (exits non-zero on failure)."""
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(e.stderr or e.stdout or str(e), file=sys.stderr)
        raise SystemExit(e.returncode or 1) from e


if __name__ == "__main__":
    quickstart_verify_main()
