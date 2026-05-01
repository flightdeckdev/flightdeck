"""Release bundle integrity (checksum) for cross-platform stable hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path

# Text-like files: normalize CRLF/CR to LF before hashing (see canonical spec-v1-forward §3 on flightdeckdev/flightdeck main).
_TEXT_SUFFIXES: frozenset[str] = frozenset(
    {".md", ".yaml", ".yml", ".txt", ".json", ".csv", ".toml"}
)
_SKIP_DIR_PARTS: frozenset[str] = frozenset({".git", "__pycache__"})


def _skip_path(path: Path, base: Path) -> bool:
    try:
        rel = path.relative_to(base)
    except ValueError:
        return True
    return any(part in _SKIP_DIR_PARTS for part in rel.parts)


def iter_bundle_files(path: Path) -> list[Path]:
    """List files contributing to the bundle hash (sorted, stable order)."""
    if path.is_file():
        return [path]
    files: list[Path] = []
    base = path
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        if p.is_symlink():
            continue
        if _skip_path(p, base):
            continue
        files.append(p)

    def sort_key(p: Path) -> str:
        return p.relative_to(base).as_posix()

    return sorted(files, key=sort_key)


def _content_bytes_for_hash(path: Path) -> bytes:
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix not in _TEXT_SUFFIXES:
        return raw
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.encode("utf-8")


def bundle_checksum(path: Path) -> str:
    """SHA-256 over canonical bundle representation (sorted paths + normalized text)."""
    files = iter_bundle_files(path)
    h = hashlib.sha256()
    base = path if path.is_dir() else path.parent
    for f in files:
        rel = f.relative_to(base).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(_content_bytes_for_hash(f))
        h.update(b"\0")
    return h.hexdigest()
