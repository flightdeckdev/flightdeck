"""Pinned SHA-256 for committed bundle fixture (CI + cross-OS regression)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from flightdeck.bundle import bundle_checksum

GOLDEN_BUNDLE_DIR = Path(__file__).resolve().parent / "fixtures" / "golden_bundle"
# Pinned digest for tests/fixtures/golden_bundle (LF, UTF-8); see canonical v1-next-steps / golden bundle CI notes.
GOLDEN_BUNDLE_SHA256 = "d016ae32d4a32667757618f8b76202ff0dfd317b3788401e3ae40622b266469d"


def test_committed_golden_bundle_matches_pinned_sha256() -> None:
    assert GOLDEN_BUNDLE_DIR.is_dir()
    assert bundle_checksum(GOLDEN_BUNDLE_DIR) == GOLDEN_BUNDLE_SHA256


@pytest.mark.skipif(os.name == "nt", reason="symlink creation often requires elevated/dev mode on Windows")
def test_bundle_checksum_ignores_symlinks(tmp_path: Path) -> None:
    shutil.copytree(GOLDEN_BUNDLE_DIR, tmp_path / "b")
    root = tmp_path / "b"
    c1 = bundle_checksum(root)
    (root / "prompts" / "link.md").symlink_to(root / "prompts" / "s.md")
    c2 = bundle_checksum(root)
    assert c1 == c2, "symlinks must not affect bundle_checksum (determinism + security)"
