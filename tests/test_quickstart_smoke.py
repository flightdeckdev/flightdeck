from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_quickstart_smoke_script_exits_zero() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "quickstart_smoke.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
