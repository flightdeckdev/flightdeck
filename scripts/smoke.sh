#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$(mktemp -d)"

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

cd "$WORKDIR"

flightdeck init
flightdeck pricing import "$ROOT/examples/quickstart/pricing-baseline.yaml"
flightdeck pricing import "$ROOT/examples/quickstart/pricing-candidate.yaml"
flightdeck policy set "$ROOT/examples/quickstart/policy.yaml"

BASELINE="$(flightdeck release register "$ROOT/examples/quickstart/baseline-release")"
CANDIDATE="$(flightdeck release register "$ROOT/examples/quickstart/candidate-release")"

cat > baseline-events.jsonl <<EOF
{"api_version":"v1","type":"run_end","timestamp":"$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")","workspace_id":"ws_local","agent_id":"agent_support","release_id":"$BASELINE","run_id":"baseline-smoke-1","tenant_id":"tenant_acme","task_id":"task_support","environment":"local","metrics":{"latency_ms":1000,"success":true,"error_type":null},"usage":{"model":{"provider":"openai","model":"gpt-4.1-mini","input_tokens":1000,"output_tokens":500,"cached_input_tokens":0},"tools":[]},"labels":{"example":"quickstart"}}
EOF

cat > candidate-events.jsonl <<EOF
{"api_version":"v1","type":"run_end","timestamp":"$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")","workspace_id":"ws_local","agent_id":"agent_support","release_id":"$CANDIDATE","run_id":"candidate-smoke-1","tenant_id":"tenant_acme","task_id":"task_support","environment":"local","metrics":{"latency_ms":1200,"success":true,"error_type":null},"usage":{"model":{"provider":"openai","model":"gpt-4.1-mini","input_tokens":1000,"output_tokens":500,"cached_input_tokens":0},"tools":[]},"labels":{"example":"quickstart"}}
EOF

flightdeck runs ingest baseline-events.jsonl
flightdeck runs ingest candidate-events.jsonl
flightdeck release diff "$BASELINE" "$CANDIDATE" --window 7d
flightdeck release promote "$BASELINE" --env local --window 7d --reason "smoke baseline"
flightdeck release history --agent agent_support --env local
