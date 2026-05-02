#!/usr/bin/env bash
# Bootstrap a throwaway workspace, mirror examples/quickstart data, run diff + verify.
# Intended for GitHub Actions and local dry-runs (bash). See examples/ci/README.md.
set -euo pipefail

WORKSPACE="${WORKSPACE:?Set WORKSPACE to an empty directory for flightdeck.yaml + SQLite}"
QUICKSTART_ROOT="${QUICKSTART_ROOT:?Set QUICKSTART_ROOT to examples/quickstart (or a copy)}"
BASELINE_PH="__BASELINE_RELEASE_ID__"
CANDIDATE_PH="__CANDIDATE_RELEASE_ID__"

if [[ -n "${FD_PROJECT:-}" ]]; then
  _fd() { ( cd "$WORKSPACE" && uv run --directory "$FD_PROJECT" flightdeck "$@"; ); }
else
  _fd() { ( cd "$WORKSPACE" && flightdeck "$@"; ); }
fi

mkdir -p "$WORKSPACE"
_fd init
_fd pricing import "$QUICKSTART_ROOT/pricing-baseline.yaml"
_fd pricing import "$QUICKSTART_ROOT/pricing-candidate.yaml"
_fd policy set "$QUICKSTART_ROOT/policy.yaml"

baseline_id="$(_fd release register "$QUICKSTART_ROOT/baseline-release" | tail -n1)"
candidate_id="$(_fd release register "$QUICKSTART_ROOT/candidate-release" | tail -n1)"

baseline_events="$WORKSPACE/baseline-events.jsonl"
candidate_events="$WORKSPACE/candidate-events.jsonl"
sed "s/${BASELINE_PH}/${baseline_id}/g" "$QUICKSTART_ROOT/baseline-events.jsonl" >"$baseline_events"
sed "s/${CANDIDATE_PH}/${candidate_id}/g" "$QUICKSTART_ROOT/candidate-events.jsonl" >"$candidate_events"

_fd runs ingest "$baseline_events"
_fd runs ingest "$candidate_events"
_fd release diff "$baseline_id" "$candidate_id" --window 7d --fail-on-policy
_fd release verify "$baseline_id" --path "$QUICKSTART_ROOT/baseline-release"
_fd release verify "$candidate_id" --path "$QUICKSTART_ROOT/candidate-release"
_fd doctor

echo "ledger-gate: OK"
