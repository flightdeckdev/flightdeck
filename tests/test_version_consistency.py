"""Keep pyproject.toml and flightdeck.__version__ aligned (release workflow assumes this)."""

from __future__ import annotations

import pathlib
import re

import tomllib

from flightdeck import __version__


def test_pyproject_version_matches_flightdeck_init() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    declared = data["project"]["version"]
    assert declared == __version__


def test_init_version_is_assignable_string() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    text = (root / "src" / "flightdeck" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    assert m is not None
    assert m.group(1) == __version__
