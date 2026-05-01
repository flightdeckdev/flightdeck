from __future__ import annotations

import os
import sys
from pathlib import Path

# pyproject.toml sets --basetemp=.tmp/pytest; pytest does not create the parent `.tmp/`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_TMP = _REPO_ROOT / ".tmp"
_REPO_TMP.mkdir(parents=True, exist_ok=True)


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

    os.environ.setdefault("TEMP", str(_REPO_TMP.resolve()))
    os.environ.setdefault("TMP", str(_REPO_TMP.resolve()))
    os.environ.setdefault("TMPDIR", str(_REPO_TMP.resolve()))
