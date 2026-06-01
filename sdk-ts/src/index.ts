// Core client and error
export { FlightDeckClient, FlightDeckError } from "./client.js";

// Adapters
export { FlightDeckOpenAIAdapter } from "./adapters/openai.js";
export type { OpenAIAdapterOptions } from "./adapters/openai.js";

// All wire types
export type {
  // RunEvent hierarchy
  RunEvent,
  RunEventRequest,
  RunEventMetrics,
  RunEventModelUsage,
  RunEventToolUsage,
  RunEventUsage,
  // Release artifact
  ReleaseArtifact,
  ReleaseMetadata,
  ReleaseSpec,
  ReleaseSpecAgent,
  ReleaseSpecRuntime,
  ReleaseSpecPrompts,
  ReleaseSpecTools,
  ReleaseSpecRouting,
  ReleaseSpecRoutingFallback,
  ReleaseSpecSafety,
  ReleaseSpecSafetyRetryPolicy,
  ReleaseSpecSafetyTimeouts,
  ReleasePricingReference,
  // Diff result
  DiffResult,
  DiffFilters,
  DiffMetrics,
  DiffSamples,
  DiffPricing,
  DiffPricingPrices,
  DiffPricingCatalog,
  PolicyResult,
  // Workspace
  WorkspaceInfo,
  // Webhook
  WebhookPayload,
  // Client options
  FlightDeckClientOptions,
} from "./types.js";
