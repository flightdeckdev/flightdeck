from __future__ import annotations

from pathlib import Path

from flightdeck.bundle import bundle_checksum


def _write_bundle(root: Path, *, newline: str) -> None:
    (root / "prompts").mkdir(parents=True)
    (root / "release.yaml").write_text(
        "api_version: v1\nkind: Release\nmetadata:\n  name: t\n  version: '1'\n"
        "spec:\n  agent:\n    agent_id: a\n  runtime:\n    provider: openai\n    model: m\n"
        "  prompts:\n    system_ref: prompts/s.md\n  pricing_reference:\n    provider: openai\n"
        "    pricing_version: p\n",
        encoding="utf-8",
        newline=newline,
    )
    (root / "prompts" / "s.md").write_bytes(f"line1{newline}line2{newline}".encode("utf-8"))


def test_bundle_checksum_stable_across_crlf_and_lf(tmp_path: Path) -> None:
    lf_dir = tmp_path / "lf"
    crlf_dir = tmp_path / "crlf"
    lf_dir.mkdir()
    crlf_dir.mkdir()
    _write_bundle(lf_dir, newline="\n")
    _write_bundle(crlf_dir, newline="\r\n")
    assert bundle_checksum(lf_dir) == bundle_checksum(crlf_dir)


def test_bundle_checksum_skips_git_dir(tmp_path: Path) -> None:
    root = tmp_path / "b"
    _write_bundle(root, newline="\n")
    without_git = bundle_checksum(root)
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    with_git = bundle_checksum(root)
    assert with_git == without_git
