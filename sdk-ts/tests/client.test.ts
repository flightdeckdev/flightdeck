/**
 * Tests for FlightDeckClient and FlightDeckOpenAIAdapter.
 * Uses vitest with vi.stubGlobal to mock the native fetch API.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FlightDeckClient, FlightDeckError } from "../src/client.js";
import { FlightDeckOpenAIAdapter } from "../src/adapters/openai.js";
import type { RunEvent, DiffResult } from "../src/types.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal valid RunEvent for tests. */
function makeRunEvent(overrides: Partial<RunEvent> = {}): RunEvent {
  return {
    timestamp: "2024-06-01T12:00:00.000Z",
    agent_id: "test-agent",
    release_id: "rel-abc123",
    run_id: "run-001",
    tenant_id: "tenant-1",
    task_id: "task-42",
    environment: "test",
    usage: {
      model: {
        provider: "openai",
        model: "gpt-4o",
        input_tokens: 100,
        output_tokens: 50,
      },
    },
    ...overrides,
  };
}

/** Construct a FlightDeckClient pointed at a fake server. */
function makeClient(overrides: { apiToken?: string; actor?: string } = {}) {
  return new FlightDeckClient({
    serverUrl: "http://localhost:7777",
    releaseId: "rel-abc123",
    ...overrides,
  });
}

/** Create a mock fetch Response. */
function mockResponse(
  body: unknown,
  status = 200
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// FlightDeckClient — ingestEvent / ingestEvents
// ---------------------------------------------------------------------------

describe("FlightDeckClient.ingestEvent", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends POST /v1/events with events array", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    const client = makeClient();
    const event = makeRunEvent();
    await client.ingestEvent(event);

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:7777/v1/events");
    expect(init.method).toBe("POST");

    const body = JSON.parse(init.body as string) as { events: RunEvent[] };
    expect(body.events).toHaveLength(1);
    expect(body.events[0].agent_id).toBe("test-agent");
    expect(body.events[0].run_id).toBe("run-001");
  });

  it("serialises all required RunEvent fields", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    const client = makeClient();
    const event = makeRunEvent({
      metrics: { latency_ms: 250, success: true },
      labels: { region: "eu-west-1" },
    });
    await client.ingestEvent(event);

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as { events: RunEvent[] };
    const sent = body.events[0];

    expect(sent.tenant_id).toBe("tenant-1");
    expect(sent.task_id).toBe("task-42");
    expect(sent.environment).toBe("test");
    expect(sent.usage.model.input_tokens).toBe(100);
    expect(sent.usage.model.output_tokens).toBe(50);
    expect(sent.metrics?.latency_ms).toBe(250);
    expect(sent.labels?.region).toBe("eu-west-1");
  });

  it("sets Authorization header when apiToken is provided", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    const client = makeClient({ apiToken: "sk-secret-token" });
    await client.ingestEvent(makeRunEvent());

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer sk-secret-token");
  });

  it("omits Authorization header when apiToken is not provided", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    const client = makeClient();
    await client.ingestEvent(makeRunEvent());

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Authorization"]).toBeUndefined();
  });

  it("sets X-FlightDeck-Actor header to 'node-sdk' by default", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    const client = makeClient();
    await client.ingestEvent(makeRunEvent());

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["X-FlightDeck-Actor"]).toBe("node-sdk");
  });

  it("allows overriding X-FlightDeck-Actor via actor option", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    const client = makeClient({ actor: "my-service" });
    await client.ingestEvent(makeRunEvent());

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["X-FlightDeck-Actor"]).toBe("my-service");
  });

  it("includes X-Request-Id header on every request", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    const client = makeClient();
    await client.ingestEvent(makeRunEvent());

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Request-Id"]).toBeTruthy();
    // Should be a UUID-like string
    expect(headers["X-Request-Id"]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    );
  });

  it("sends a batch of events via ingestEvents", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse({ inserted: 3 }));

    const client = makeClient();
    const events = [
      makeRunEvent({ run_id: "run-001" }),
      makeRunEvent({ run_id: "run-002" }),
      makeRunEvent({ run_id: "run-003" }),
    ];
    await client.ingestEvents(events);

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as { events: RunEvent[] };
    expect(body.events).toHaveLength(3);
    expect(body.events.map((e) => e.run_id)).toEqual(["run-001", "run-002", "run-003"]);
  });

  it("throws FlightDeckError on 4xx non-retryable response", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      mockResponse({ detail: "Unauthorized" }, 401)
    );

    const client = makeClient();
    await expect(client.ingestEvent(makeRunEvent())).rejects.toThrow(FlightDeckError);
  });

  it("retries on 429 and succeeds on third attempt", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch
      .mockResolvedValueOnce(mockResponse({ detail: "rate limited" }, 429))
      .mockResolvedValueOnce(mockResponse({ detail: "rate limited" }, 429))
      .mockResolvedValueOnce(mockResponse({ inserted: 1 }));

    // Patch sleep so the test doesn't wait for real backoff
    vi.stubGlobal(
      "setTimeout",
      (fn: () => void) => { fn(); return 0; }
    );

    const client = makeClient();
    await client.ingestEvent(makeRunEvent()); // should not throw

    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
});

// ---------------------------------------------------------------------------
// FlightDeckClient — diff()
// ---------------------------------------------------------------------------

describe("FlightDeckClient.diff", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const fakeDiffResult: DiffResult = {
    window: "24h",
    since: "2024-05-31T12:00:00Z",
    until: "2024-06-01T12:00:00Z",
    filters: {
      environment: "production",
      tenant_id: null,
      task_id: null,
    },
    pricing: {
      baseline_provider: "openai",
      baseline_version: "2024-01",
      baseline_model: "gpt-4o",
      candidate_provider: "openai",
      candidate_version: "2024-01",
      candidate_model: "gpt-4o",
      pricing_or_model_changed: false,
      prices: {
        baseline_input_usd_per_1k_tokens: 0.005,
        baseline_output_usd_per_1k_tokens: 0.015,
        baseline_cached_input_usd_per_1k_tokens: null,
        candidate_input_usd_per_1k_tokens: 0.005,
        candidate_output_usd_per_1k_tokens: 0.015,
        candidate_cached_input_usd_per_1k_tokens: null,
      },
      warnings: [],
      hints: [],
      catalog: {
        enabled: false,
        catalog_version: null,
        baseline_slot_id: null,
        candidate_slot_id: null,
        baseline_cost_per_run_usd: null,
        candidate_cost_per_run_usd: null,
        delta_cost_per_run_usd: null,
        warnings: [],
      },
    },
    samples: {
      baseline_runs: 1200,
      candidate_runs: 850,
      confidence: "HIGH",
      confidence_reason: null,
    },
    metrics: {
      baseline_cost_per_run_usd: 0.0012,
      candidate_cost_per_run_usd: 0.0011,
      delta_cost_per_run_usd: -0.0001,
      delta_cost_per_run_pct: -8.33,
      baseline_latency_ms_avg: 320,
      candidate_latency_ms_avg: 295,
      delta_latency_ms_avg: -25,
      baseline_error_rate: 0.01,
      candidate_error_rate: 0.008,
      delta_error_rate: -0.002,
    },
    policy: {
      passed: true,
      reasons: [],
      evaluated_at: "2024-06-01T12:00:00Z",
    },
  };

  it("sends POST /v1/diff with correct body", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse(fakeDiffResult));

    const client = makeClient();
    await client.diff({
      baselineReleaseId: "rel-v1",
      candidateReleaseId: "rel-v2",
      window: "48h",
      environment: "production",
    });

    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:7777/v1/diff");
    expect(init.method).toBe("POST");

    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.baseline_release_id).toBe("rel-v1");
    expect(body.candidate_release_id).toBe("rel-v2");
    expect(body.window).toBe("48h");
    expect(body.environment).toBe("production");
  });

  it("defaults window to '24h' when not specified", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse(fakeDiffResult));

    const client = makeClient();
    await client.diff({
      baselineReleaseId: "rel-v1",
      candidateReleaseId: "rel-v2",
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.window).toBe("24h");
  });

  it("parses DiffResult and exposes policy.passed", async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse(fakeDiffResult));

    const client = makeClient();
    const result = await client.diff({
      baselineReleaseId: "rel-v1",
      candidateReleaseId: "rel-v2",
    });

    expect(result.policy.passed).toBe(true);
    expect(result.policy.reasons).toHaveLength(0);
    expect(result.samples.confidence).toBe("HIGH");
    expect(result.metrics.delta_cost_per_run_usd).toBe(-0.0001);
  });

  it("surfaces policy failure reasons correctly", async () => {
    const failedDiff: DiffResult = {
      ...fakeDiffResult,
      policy: {
        passed: false,
        reasons: ["candidate error_rate 0.0500 exceeds max 0.0200"],
        evaluated_at: "2024-06-01T12:00:00Z",
      },
    };
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(mockResponse(failedDiff));

    const client = makeClient();
    const result = await client.diff({
      baselineReleaseId: "rel-v1",
      candidateReleaseId: "rel-v2",
    });

    expect(result.policy.passed).toBe(false);
    expect(result.policy.reasons[0]).toContain("error_rate");
  });
});

// ---------------------------------------------------------------------------
// FlightDeckOpenAIAdapter
// ---------------------------------------------------------------------------

describe("FlightDeckOpenAIAdapter", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /** Minimal mock OpenAI client that resolves immediately. */
  function makeOpenAIMock(overrides: {
    prompt_tokens?: number;
    completion_tokens?: number;
    finish_reason?: string;
    model?: string;
    cached_tokens?: number;
  } = {}) {
    const {
      prompt_tokens = 200,
      completion_tokens = 80,
      finish_reason = "stop",
      model = "gpt-4o",
      cached_tokens = 0,
    } = overrides;

    const completion = {
      id: "chatcmpl-test123",
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: "Hello!" },
          finish_reason,
        },
      ],
      usage: {
        prompt_tokens,
        completion_tokens,
        total_tokens: prompt_tokens + completion_tokens,
        prompt_tokens_details: { cached_tokens },
      },
    };

    return {
      chat: {
        completions: {
          create: vi.fn().mockResolvedValue(completion),
        },
      },
    };
  }

  it("returns the original OpenAI response unchanged", async () => {
    // Suppress the fire-and-forget ingest call
    vi.mocked(fetch).mockResolvedValue(mockResponse({ inserted: 1 }));

    const client = makeClient({ apiToken: "tok" });
    const adapter = new FlightDeckOpenAIAdapter(client);
    const openai = makeOpenAIMock();

    const result = await adapter.chatCompletionsCreate(
      openai as unknown as import("openai").default,
      { model: "gpt-4o", messages: [{ role: "user", content: "Hi" }] }
    );

    expect(result.choices[0].finish_reason).toBe("stop");
    expect(result.model).toBe("gpt-4o");
  });

  it("records input_tokens and output_tokens from OpenAI usage", async () => {
    vi.mocked(fetch).mockResolvedValue(mockResponse({ inserted: 1 }));

    const client = makeClient();
    const adapter = new FlightDeckOpenAIAdapter(client);
    const openai = makeOpenAIMock({ prompt_tokens: 150, completion_tokens: 60 });

    await adapter.chatCompletionsCreate(
      openai as unknown as import("openai").default,
      { model: "gpt-4o", messages: [{ role: "user", content: "Hi" }] }
    );

    // Give the fire-and-forget promise a tick to settle
    await new Promise((r) => setTimeout(r, 0));

    expect(fetch).toHaveBeenCalledOnce();
    const [, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as { events: RunEvent[] };
    const modelUsage = body.events[0].usage.model;

    expect(modelUsage.input_tokens).toBe(150);
    expect(modelUsage.output_tokens).toBe(60);
    expect(modelUsage.provider).toBe("openai");
    expect(modelUsage.model).toBe("gpt-4o");
  });

  it("records latency_ms > 0", async () => {
    vi.mocked(fetch).mockResolvedValue(mockResponse({ inserted: 1 }));

    const client = makeClient();
    const adapter = new FlightDeckOpenAIAdapter(client);

    // Delay the OpenAI mock by 10ms so latency is measurable
    const openai = {
      chat: {
        completions: {
          create: vi.fn().mockImplementation(
            () =>
              new Promise((resolve) =>
                setTimeout(
                  () =>
                    resolve({
                      id: "chatcmpl-x",
                      object: "chat.completion",
                      created: Math.floor(Date.now() / 1000),
                      model: "gpt-4o",
                      choices: [{ index: 0, message: { role: "assistant", content: "Hi" }, finish_reason: "stop" }],
                      usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
                    }),
                  10
                )
              )
          ),
        },
      },
    };

    await adapter.chatCompletionsCreate(
      openai as unknown as import("openai").default,
      { model: "gpt-4o", messages: [{ role: "user", content: "Hi" }] }
    );

    await new Promise((r) => setTimeout(r, 0));

    const [, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as { events: RunEvent[] };
    const latency = body.events[0].metrics?.latency_ms;

    expect(latency).toBeGreaterThan(0);
  });

  it("marks success=false when finish_reason is not 'stop'", async () => {
    vi.mocked(fetch).mockResolvedValue(mockResponse({ inserted: 1 }));

    const client = makeClient();
    const adapter = new FlightDeckOpenAIAdapter(client);
    const openai = makeOpenAIMock({ finish_reason: "length" });

    await adapter.chatCompletionsCreate(
      openai as unknown as import("openai").default,
      { model: "gpt-4o", messages: [{ role: "user", content: "Hi" }] }
    );

    await new Promise((r) => setTimeout(r, 0));

    const [, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as { events: RunEvent[] };
    const metrics = body.events[0].metrics;

    expect(metrics?.success).toBe(false);
    expect(metrics?.error_type).toBe("finish_reason:length");
  });

  it("extracts cached_input_tokens from prompt_tokens_details", async () => {
    vi.mocked(fetch).mockResolvedValue(mockResponse({ inserted: 1 }));

    const client = makeClient();
    const adapter = new FlightDeckOpenAIAdapter(client);
    const openai = makeOpenAIMock({ cached_tokens: 50 });

    await adapter.chatCompletionsCreate(
      openai as unknown as import("openai").default,
      { model: "gpt-4o", messages: [{ role: "user", content: "Hi" }] }
    );

    await new Promise((r) => setTimeout(r, 0));

    const [, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as { events: RunEvent[] };
    expect(body.events[0].usage.model.cached_input_tokens).toBe(50);
  });

  it("does not throw when FlightDeck ingest fails (fire-and-forget)", async () => {
    // Simulate a server error — adapter should not surface this to the caller
    vi.mocked(fetch).mockResolvedValue(mockResponse({ detail: "server error" }, 500));

    // Also mock additional retries as 500
    vi.mocked(fetch).mockResolvedValue(mockResponse({ detail: "server error" }, 500));

    const client = makeClient();
    const adapter = new FlightDeckOpenAIAdapter(client);
    const openai = makeOpenAIMock();

    // Should resolve without throwing despite ingest failure
    await expect(
      adapter.chatCompletionsCreate(
        openai as unknown as import("openai").default,
        { model: "gpt-4o", messages: [{ role: "user", content: "Hi" }] }
      )
    ).resolves.toBeDefined();
  });
});
