/**
 * FlightDeck adapter for the OpenAI Node.js SDK.
 *
 * This adapter wraps `openai.chat.completions.create()` (non-streaming),
 * measures latency, extracts token counts, and ingests a RunEvent into
 * FlightDeck — all without modifying the return value seen by the caller.
 *
 * The `openai` package is an optional peer dependency; the adapter imports it
 * as a type-only import so the rest of the SDK remains zero-dependency.
 */

import type OpenAI from "openai";
import { FlightDeckClient } from "../client.js";
import type { RunEvent } from "../types.js";

export interface OpenAIAdapterOptions {
  /**
   * Override the FlightDeck agent_id for events recorded by this adapter.
   * Defaults to "openai-agent".
   */
  agentId?: string;
  /**
   * Override the tenant_id recorded on events.
   * Defaults to "default".
   */
  tenantId?: string;
  /**
   * Override the task_id recorded on events.
   * Defaults to "openai-chat".
   */
  taskId?: string;
  /**
   * Deployment environment (e.g. "production", "staging").
   * Defaults to "production".
   */
  environment?: string;
}

export class FlightDeckOpenAIAdapter {
  private readonly client: FlightDeckClient;
  private readonly agentId: string;
  private readonly tenantId: string;
  private readonly taskId: string;
  private readonly environment: string;

  constructor(client: FlightDeckClient, options: OpenAIAdapterOptions = {}) {
    this.client = client;
    this.agentId = options.agentId ?? "openai-agent";
    this.tenantId = options.tenantId ?? "default";
    this.taskId = options.taskId ?? "openai-chat";
    this.environment = options.environment ?? "production";
  }

  /**
   * Drop-in wrapper for `openai.chat.completions.create()` (non-streaming).
   *
   * Behaviour:
   *  - Calls the OpenAI API exactly once.
   *  - Records wall-clock latency, token counts, model name, and finish_reason.
   *  - Ingests a `run_end` RunEvent into FlightDeck (fire-and-forget; errors
   *    are swallowed so they never surface to the caller).
   *  - Returns the original `ChatCompletion` object unchanged.
   *
   * @param openai  An initialised `OpenAI` instance.
   * @param params  Non-streaming chat completion params (same as you'd pass
   *                to `openai.chat.completions.create` directly).
   */
  async chatCompletionsCreate(
    openai: OpenAI,
    params: OpenAI.Chat.ChatCompletionCreateParamsNonStreaming
  ): Promise<OpenAI.Chat.ChatCompletion> {
    const startMs = Date.now();
    const runId = crypto.randomUUID();
    const timestamp = new Date(startMs).toISOString();

    const completion = await openai.chat.completions.create(params);

    const latencyMs = Date.now() - startMs;

    const usage = completion.usage;
    const finishReason = completion.choices[0]?.finish_reason;

    const event: RunEvent = {
      api_version: "v1",
      type: "run_end",
      timestamp,
      agent_id: this.agentId,
      release_id: this.client.defaultReleaseId,
      run_id: runId,
      tenant_id: this.tenantId,
      task_id: this.taskId,
      environment: this.environment,
      metrics: {
        latency_ms: latencyMs,
        success: finishReason === "stop",
        error_type: finishReason !== "stop" ? `finish_reason:${finishReason}` : null,
      },
      usage: {
        model: {
          provider: "openai",
          model: params.model,
          input_tokens: usage?.prompt_tokens ?? 0,
          output_tokens: usage?.completion_tokens ?? 0,
          cached_input_tokens:
            (usage as OpenAI.CompletionUsage & { prompt_tokens_details?: { cached_tokens?: number } })
              ?.prompt_tokens_details?.cached_tokens ?? 0,
        },
        tools: [],
      },
      labels: {
        sdk_adapter: "openai",
      },
    };

    // Fire-and-forget — ingest errors must not surface to the caller
    this.client.ingestEvent(event).catch(() => {
      // Intentionally swallowed
    });

    return completion;
  }
}
