#!/usr/bin/env bash
# Run optional PostgreSQL storage tests. See scripts/run_postgres_tests.ps1 for full notes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export FLIGHTDECK_TEST_POSTGRES_URL="${FLIGHTDECK_TEST_POSTGRES_URL:-postgresql://postgres:test@127.0.0.1:5432/flightdeck_test}"
if [[ "${1:-}" == "--docker" ]]; then
  docker rm -f fd-pg-test 2>/dev/null || true
  docker run -d --name fd-pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=flightdeck_test -p 5432:5432 postgres:16
  sleep 6
  trap 'docker rm -f fd-pg-test 2>/dev/null || true' EXIT
fi
uv run python -c "import psycopg"
uv run python -m pytest tests/test_storage_postgres.py -v --tb=short
