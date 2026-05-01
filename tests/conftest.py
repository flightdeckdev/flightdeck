from __future__ import annotations

import os
import sys
from pathlib import Path


def pytest_configure() -> None:
    """
    Windows note:

    Some environments restrict the default OS temp directory used by pytest's `tmp_path` fixture.
    Redirect pytest temp dirs into a repo-local `.tmp/` folder unless the user opts out.
    """
    if os.environ.get("FLIGHTDECK_USE_SYSTEM_TEMP") == "1":
        return
    if sys.platform != "win32":
        return

    tmp_dir = (Path.cwd() / ".tmp").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("TEMP", str(tmp_dir))
    os.environ.setdefault("TMP", str(tmp_dir))
    os.environ.setdefault("TMPDIR", str(tmp_dir))
