/**
 * Minimal POST /v1/events sample (Node 18+ with global fetch, or Node 20+).
 *
 *   node examples/integration/emit_sample_events.node.mjs \
 *     --base-url http://127.0.0.1:8765 \
 *     --release-id rel_yourregisteredid \
 *     --agent-id agent_support
 *
 * Same envelope as emit_sample_events.py: { "events": [ RunEvent, ... ] }.
 */
function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  if (i === -1 || i + 1 >= process.argv.length) return fallback;
  return process.argv[i + 1];
}

const baseUrl = (arg("--base-url", "http://127.0.0.1:8765") ?? "http://127.0.0.1:8765").replace(/\/$/, "");
const releaseId = arg("--release-id");
const agentId = arg("--agent-id");
const environment = arg("--environment", "local") ?? "local";

if (!releaseId || !agentId) {
  console.error("Usage: node emit_sample_events.node.mjs --release-id REL --agent-id AGENT [--base-url URL] [--environment ENV]");
  process.exit(2);
}

const rid = Math.random().toString(16).slice(2, 12);
const ts = new Date().toISOString();

const event = {
  api_version: "v1",
  type: "run_end",
  timestamp: ts,
  workspace_id: "ws_local",
  agent_id: agentId,
  release_id: releaseId,
  run_id: `emit-sample-node-${rid}`,
  tenant_id: "tenant_example",
  task_id: "task_example",
  environment,
  metrics: { latency_ms: 250, success: true, error_type: null },
  usage: {
    model: {
      provider: "openai",
      model: "gpt-4.1-mini",
      input_tokens: 400,
      output_tokens: 120,
      cached_input_tokens: 0,
    },
    tools: [],
  },
  labels: { source: "examples/integration/emit_sample_events.node.mjs" },
};

const body = JSON.stringify({ events: [event] });

const url = `${baseUrl}/v1/events`;
const res = await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body,
});

const text = await res.text();
if (!res.ok) {
  console.error(`HTTP ${res.status}: ${text}`);
  process.exit(1);
}
console.log(`POST ${url} -> ${res.status}`);
console.log(text);
