# flightdeck-ai (Node.js / TypeScript SDK)

TypeScript/Node.js SDK for [FlightDeck](https://github.com/flightdeckdev/flightdeck) — AI release governance for production agents.

FlightDeck versions agent releases, ingests runtime evidence (cost/latency/errors), diffs builds, and policy-gates promote/rollback decisions. This SDK lets Node.js and TypeScript agents ingest evidence without writing raw HTTP.

## Install

```bash
npm install flightdeck-ai
```

Requires Node.js 18+ (uses the built-in `fetch` API). Zero runtime dependencies.

If you use the OpenAI adapter, install `openai` as a peer dependency:

```bash
npm install openai
```

## Quickstart

```typescript
import { FlightDeckClient } from "flightdeck-ai";

const flightdeck = new FlightDeckClient({
  serverUrl: "http://localhost:7777",   // or your deployed FlightDeck URL
  apiToken: process.env.FLIGHTDECK_TOKEN,
  releaseId: "rel-my-agent-v1.2.0",
});

// Ingest a run event after your agent completes a task
await flightdeck.ingestEvent({
  timestamp: new Date().toISOString(),
  agent_id: "my-agent",
  release_id: "rel-my-agent-v1.2.0",
  run_id: crypto.randomUUID(),
  tenant_id: "tenant-acme",
  task_id: "order-summary-42",
  environment: "production",
  metrics: { latency_ms: 312, success: true },
  usage: {
    model: {
      provider: "openai",
      model: "gpt-4o",
      input_tokens: 850,
      output_tokens: 220,
    },
  },
});

// Diff two releases and check the policy gate before promoting
const diff = await flightdeck.diff({
  baselineReleaseId: "rel-my-agent-v1.1.0",
  candidateReleaseId: "rel-my-agent-v1.2.0",
  window: "24h",
  environment: "production",
});

if (diff.policy.passed) {
  console.log("Policy passed — safe to promote!");
  console.log(`Cost delta: ${diff.metrics.delta_cost_per_run_usd.toFixed(6)} USD/run`);
} else {
  console.error("Policy blocked promotion:", diff.policy.reasons);
}
```

## OpenAI Adapter

Drop-in wrapper for `openai.chat.completions.create()`. Automatically measures latency, extracts token counts, and ingests a `RunEvent` into FlightDeck without modifying the response your code receives.

```typescript
import OpenAI from "openai";
import { FlightDeckClient } from "flightdeck-ai";
import { FlightDeckOpenAIAdapter } from "flightdeck-ai/adapters/openai";

const openai = new OpenAI();
const flightdeck = new FlightDeckClient({ serverUrl: "http://localhost:7777", releaseId: "rel-v1" });
const adapter = new FlightDeckOpenAIAdapter(flightdeck, { environment: "production" });

// Use exactly like openai.chat.completions.create — the response is unchanged
const completion = await adapter.chatCompletionsCreate(openai, {
  model: "gpt-4o",
  messages: [{ role: "user", content: "Summarise this order for me." }],
});
```

Ingest errors are swallowed so they never surface to the caller — your agent keeps running even if the FlightDeck server is unreachable.

## API Reference

### `FlightDeckClient`

| Method | Description |
|--------|-------------|
| `ingestEvent(event)` | Ingest a single `RunEvent` via `POST /v1/events` |
| `ingestEvents(events[])` | Ingest a batch of `RunEvent`s in one request |
| `diff(options)` | Diff two releases via `POST /v1/diff`, returns a `DiffResult` |
| `getWorkspace()` | Read workspace metadata via `GET /v1/workspace` |
| `health()` | Health check via `GET /health` |

All methods retry on `429` and `5xx` responses with exponential backoff (max 3 attempts). Failed requests throw `FlightDeckError` with `statusCode`, `detail`, and `requestId` fields.

### `FlightDeckOpenAIAdapter`

| Method | Description |
|--------|-------------|
| `chatCompletionsCreate(openai, params)` | Wraps `openai.chat.completions.create()`, ingests a `RunEvent`, returns the original response |

### Constructor options

```typescript
new FlightDeckClient({
  serverUrl: string;      // FlightDeck server base URL (required)
  releaseId: string;      // Default release ID for events (required)
  apiToken?: string;      // Bearer token for authenticated endpoints
  actor?: string;         // Audit actor label (default: "node-sdk")
})
```

## Full HTTP API reference

See the [FlightDeck Python docs](https://github.com/flightdeckdev/flightdeck) for the complete HTTP API, CLI reference, release artifact schema, and policy configuration.

## License

Apache-2.0
