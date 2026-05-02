from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_quickstart_smoke_script_exits_zero() -> None:
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "flightdeck.quickstart_smoke"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
