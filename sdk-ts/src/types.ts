/**
 * Wire types for the FlightDeck v1 HTTP API.
 *
 * Field names and required/optional designations are derived from:
 *   - schemas/v1/run_event.schema.json
 *   - src/flightdeck/models.py  (RunEvent, RunEventMetrics, RunEventModelUsage,
 *                                 RunEventToolUsage, RunEventUsage, RunEventRequest,
 *                                 ReleaseArtifact, PolicyResult)
 *   - src/flightdeck/operations.py  (DiffOutcome / diff_outcome_to_public_dict)
 */

// ---------------------------------------------------------------------------
// RunEvent sub-types
// ---------------------------------------------------------------------------

/** Distributed-tracing context attached to a run (all optional). */
export interface RunEventRequest {
  session_id?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
}

/** Success/latency/error classification for one run. */
export interface RunEventMetrics {
  /** Wall-clock latency of the run in milliseconds. */
  latency_ms?: number | null;
  /** Whether the run completed successfully. Defaults to true. */
  success?: boolean;
  /** Error classifier string (e.g. "rate_limit", "timeout"). */
  error_type?: string | null;
}

/** Token usage and pricing context for the model call within a run. */
export interface RunEventModelUsage {
  /** LLM provider identifier (e.g. "openai", "anthropic"). */
  provider: string;
  /** Model name as returned by the provider (e.g. "gpt-4o"). */
  model: string;
  /** Number of prompt/input tokens consumed. */
  input_tokens: number;
  /** Number of completion/output tokens generated. */
  output_tokens: number;
  /** Cached/prefix-cache input tokens (default 0). */
  cached_input_tokens?: number;
}

/** Usage record for a single tool invoked during a run. */
export interface RunEventToolUsage {
  /** Canonical tool name. */
  tool_name: string;
  /** Number of times the tool was called (default 0). */
  invocations?: number;
  /** Vendor-specific cost units (default 0). */
  cost_units?: number;
}

/** Aggregate resource usage for a run (model + optional tools). */
export interface RunEventUsage {
  model: RunEventModelUsage;
  /** Tool usage records (empty array if no tools were called). */
  tools?: RunEventToolUsage[];
}

// ---------------------------------------------------------------------------
// RunEvent — top-level event ingested via POST /v1/events
// ---------------------------------------------------------------------------

/**
 * A single agent run event. Required fields match the JSON schema at
 * schemas/v1/run_event.schema.json.
 */
export interface RunEvent {
  /** Always "v1". */
  api_version?: "v1";
  /** "run_start" or "run_end" (default "run_end"). */
  type?: "run_start" | "run_end";
  /** ISO-8601 datetime with timezone. */
  timestamp: string;

  /** Workspace identifier (default "ws_local"). */
  workspace_id?: string;
  /** Stable agent identifier (matches the release artifact). */
  agent_id: string;
  /** Release identifier this run was executed under. */
  release_id: string;
  /** Unique identifier for this agent run. */
  run_id: string;

  /** Tenant identifier (for multi-tenant deployments). */
  tenant_id: string;
  /** Task/request identifier correlating multiple runs. */
  task_id: string;
  /** Deployment environment (e.g. "production", "staging"). */
  environment: string;

  /** Optional distributed-tracing context. */
  request?: RunEventRequest | null;
  /** Run outcome metrics. */
  metrics?: RunEventMetrics;
  /** Resource usage for the run (required). */
  usage: RunEventUsage;
  /** Arbitrary string key-value labels for filtering. */
  labels?: Record<string, string>;
}

// ---------------------------------------------------------------------------
// ReleaseArtifact metadata
// ---------------------------------------------------------------------------

export interface ReleaseMetadata {
  name: string;
  version: string;
  description?: string | null;
  created_by?: string | null;
  created_at?: string | null;
}

export interface ReleaseSpecAgent {
  agent_id: string;
  entrypoint?: string | null;
}

export interface ReleaseSpecRuntime {
  provider: string;
  model: string;
  temperature?: number | null;
  max_output_tokens?: number | null;
}

export interface ReleaseSpecPrompts {
  system_ref: string;
  template_refs?: string[];
}

export interface ReleaseSpecTools {
  manifest_ref?: string | null;
  tool_names?: string[];
}

export interface ReleaseSpecRoutingFallback {
  model: string;
  on_error?: boolean;
}

export interface ReleaseSpecRouting {
  strategy?: "single_model" | "fallback_model";
  fallback?: ReleaseSpecRoutingFallback | null;
}

export interface ReleaseSpecSafetyRetryPolicy {
  max_retries?: number;
  backoff_ms?: number | null;
}

export interface ReleaseSpecSafetyTimeouts {
  model_call?: number | null;
  tool_call?: number | null;
}

export interface ReleaseSpecSafety {
  retry_policy?: ReleaseSpecSafetyRetryPolicy;
  timeouts_ms?: ReleaseSpecSafetyTimeouts | null;
}

export interface ReleasePricingReference {
  provider: string;
  pricing_version: string;
}

export interface ReleaseSpec {
  agent: ReleaseSpecAgent;
  runtime: ReleaseSpecRuntime;
  prompts: ReleaseSpecPrompts;
  tools?: ReleaseSpecTools | null;
  routing?: ReleaseSpecRouting | null;
  safety?: ReleaseSpecSafety | null;
  pricing_reference: ReleasePricingReference;
  tags?: Record<string, string>;
}

/** Versioned release artifact (mirrors models.ReleaseArtifact). */
export interface ReleaseArtifact {
  api_version?: "v1";
  kind?: "Release";
  metadata: ReleaseMetadata;
  spec: ReleaseSpec;
}

// ---------------------------------------------------------------------------
// DiffResult — response from POST /v1/diff
// ---------------------------------------------------------------------------

/** Policy evaluation result embedded in a DiffResult. */
export interface PolicyResult {
  passed: boolean;
  reasons: string[];
  evaluated_at: string;
}

export interface DiffFilters {
  environment: string;
  tenant_id: string | null;
  task_id: string | null;
}

export interface DiffPricingCatalog {
  enabled: boolean;
  catalog_version: string | null;
  baseline_slot_id: string | null;
  candidate_slot_id: string | null;
  baseline_cost_per_run_usd: number | null;
  candidate_cost_per_run_usd: number | null;
  delta_cost_per_run_usd: number | null;
  warnings: string[];
}

export interface DiffPricingPrices {
  baseline_input_usd_per_1k_tokens: number | null;
  baseline_output_usd_per_1k_tokens: number | null;
  baseline_cached_input_usd_per_1k_tokens: number | null;
  candidate_input_usd_per_1k_tokens: number | null;
  candidate_output_usd_per_1k_tokens: number | null;
  candidate_cached_input_usd_per_1k_tokens: number | null;
}

export interface DiffPricing {
  baseline_provider: string;
  baseline_version: string;
  baseline_model: string;
  candidate_provider: string;
  candidate_version: string;
  candidate_model: string;
  pricing_or_model_changed: boolean;
  prices: DiffPricingPrices;
  warnings: string[];
  hints: string[];
  catalog: DiffPricingCatalog;
}

export interface DiffSamples {
  baseline_runs: number;
  candidate_runs: number;
  /** "HIGH", "LOW", or "INSUFFICIENT" */
  confidence: string;
  confidence_reason: string | null;
}

export interface DiffMetrics {
  baseline_cost_per_run_usd: number;
  candidate_cost_per_run_usd: number;
  delta_cost_per_run_usd: number;
  delta_cost_per_run_pct: number | null;
  baseline_latency_ms_avg: number | null;
  candidate_latency_ms_avg: number | null;
  delta_latency_ms_avg: number | null;
  baseline_error_rate: number;
  candidate_error_rate: number;
  delta_error_rate: number;
}

/**
 * Full response from POST /v1/diff.
 * The `policy` field is the key gate: check `policy.passed` before promoting.
 */
export interface DiffResult {
  window: string;
  since: string;
  until: string;
  filters: DiffFilters;
  pricing: DiffPricing;
  samples: DiffSamples;
  metrics: DiffMetrics;
  policy: PolicyResult;
}

// ---------------------------------------------------------------------------
// Workspace
// ---------------------------------------------------------------------------

/** Response from GET /v1/workspace. */
export interface WorkspaceInfo {
  api_version: "v1";
  kind: "WorkspacePublic";
  promotion_requires_approval: boolean;
  pricing_catalog_configured: boolean;
  server_version: string;
}

// ---------------------------------------------------------------------------
// Webhook payload envelope
// ---------------------------------------------------------------------------

/** Envelope shape for outbound webhook payloads dispatched by FlightDeck. */
export interface WebhookPayload {
  /** Webhook event type (e.g. "promote.succeeded", "rollback.succeeded"). */
  event: string;
  /** ISO-8601 timestamp when the event was dispatched. */
  dispatched_at: string;
  /** Webhook registration identifier. */
  webhook_id: string;
  /** Arbitrary event-specific payload body. */
  data: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Client options
// ---------------------------------------------------------------------------

/** Options for constructing a FlightDeckClient. */
export interface FlightDeckClientOptions {
  /** Base URL of the FlightDeck server (e.g. "http://localhost:7777"). */
  serverUrl: string;
  /** Bearer token for authenticated endpoints. */
  apiToken?: string;
  /** Default release ID attached to events when not overridden per-event. */
  releaseId: string;
  /**
   * Actor identity written to audit logs for mutation requests.
   * Defaults to "node-sdk".
   */
  actor?: string;
}
