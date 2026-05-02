#!/usr/bin/env bash
# Thin wrapper: the canonical gate is ledger_gate.py (cross-platform; no CRLF/shebang issues).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
exec "$PY" "$ROOT/ledger_gate.py"
