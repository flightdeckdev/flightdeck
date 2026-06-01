"""Cross-platform quickstart smoke: mirrors ``examples/quickstart`` in a temp workspace."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from flightdeck.demo_flow import flightdeck_argv, quickstart_root, run_quickstart_verify


def main() -> None:
    fd = flightdeck_argv()
    qs = quickstart_root()
    with tempfile.TemporaryDirectory(prefix="fd_qs_", ignore_cleanup_errors=True) as tmp_s:
        tmp = Path(tmp_s)
        run_quickstart_verify(tmp, qs, fd)

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
