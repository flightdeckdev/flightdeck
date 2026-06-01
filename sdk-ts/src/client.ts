import { randomUUID } from "node:crypto";
import type {
  DiffResult,
  FlightDeckClientOptions,
  RunEvent,
  WorkspaceInfo,
} from "./types.js";

const MAX_RETRIES = 3;
const RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504]);

/** @internal Delay helper — resolves after `ms` milliseconds. */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** @internal Compute exponential-backoff delay for attempt `n` (0-indexed). */
function backoffMs(attempt: number): number {
  // 200 ms * 2^attempt with ±10 % jitter, capped at 10 s
  const base = 200 * Math.pow(2, attempt);
  const jitter = base * 0.1 * (Math.random() * 2 - 1);
  return Math.min(base + jitter, 10_000);
}

export class FlightDeckClient {
  private readonly serverUrl: string;
  private readonly apiToken: string | undefined;
  private readonly releaseId: string;
  private readonly actor: string;

  constructor(options: FlightDeckClientOptions) {
    // Strip trailing slash so we can always prepend a path with a leading slash
    this.serverUrl = options.serverUrl.replace(/\/+$/, "");
    this.apiToken = options.apiToken;
    this.releaseId = options.releaseId;
    this.actor = options.actor ?? "node-sdk";
  }

  // ---------------------------------------------------------------------------
  // Low-level HTTP helpers
  // ---------------------------------------------------------------------------

  /** @internal Build the standard request headers. */
  private buildHeaders(requestId: string): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-FlightDeck-Actor": this.actor,
      "X-Request-Id": requestId,
    };
    if (this.apiToken) {
      headers["Authorization"] = `Bearer ${this.apiToken}`;
    }
    return headers;
  }

  /**
   * @internal Make an HTTP request with retry on 429/5xx.
   * Throws a FlightDeckError on non-retryable failure or after exhausting retries.
   */
  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.serverUrl}${path}`;
    const requestId = randomUUID();
    const headers = this.buildHeaders(requestId);

    let lastError: FlightDeckError | undefined;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      if (attempt > 0) {
        await sleep(backoffMs(attempt - 1));
      }

      let response: Response;
      try {
        response = await fetch(url, {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
        });
      } catch (err) {
        // Network-level failure — retry
        lastError = new FlightDeckError(
          `Network error calling ${method} ${path}: ${String(err)}`,
          0,
          null,
          requestId
        );
        continue;
      }

      if (response.ok) {
        // Parse JSON only if there's a body (204 No Content has none)
        if (response.status === 204) {
          return undefined as unknown as T;
        }
        return (await response.json()) as T;
      }

      if (RETRYABLE_STATUS.has(response.status)) {
        let detail: unknown = null;
        try {
          detail = await response.json();
        } catch {
          // ignore parse failure
        }
        lastError = new FlightDeckError(
          `FlightDeck server returned ${response.status} for ${method} ${path}`,
          response.status,
          detail,
          requestId
        );
        continue;
      }

      // Non-retryable HTTP error — surface immediately
      let detail: unknown = null;
      try {
        detail = await response.json();
      } catch {
        // ignore
      }
      throw new FlightDeckError(
        `FlightDeck server returned ${response.status} for ${method} ${path}`,
        response.status,
        detail,
        requestId
      );
    }

    throw (
      lastError ??
      new FlightDeckError(`Failed after ${MAX_RETRIES} attempts`, 0, null, requestId)
    );
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Ingest a batch of RunEvents.
   * Wraps `POST /v1/events { events: [...] }`.
   */
  async ingestEvents(events: RunEvent[]): Promise<void> {
    await this.request<{ inserted: number }>("POST", "/v1/events", { events });
  }

  /**
   * Convenience wrapper — ingest a single RunEvent.
   */
  async ingestEvent(event: RunEvent): Promise<void> {
    return this.ingestEvents([event]);
  }

  /**
   * Run a diff between two releases.
   * Wraps `POST /v1/diff`.
   */
  async diff(options: {
    baselineReleaseId: string;
    candidateReleaseId: string;
    window?: string;
    environment?: string;
    tenantId?: string;
    taskId?: string;
  }): Promise<DiffResult> {
    return this.request<DiffResult>("POST", "/v1/diff", {
      baseline_release_id: options.baselineReleaseId,
      candidate_release_id: options.candidateReleaseId,
      window: options.window ?? "24h",
      environment: options.environment ?? null,
      tenant_id: options.tenantId ?? null,
      task_id: options.taskId ?? null,
    });
  }

  /**
   * Retrieve read-only workspace metadata.
   * Wraps `GET /v1/workspace`.
   */
  async getWorkspace(): Promise<WorkspaceInfo> {
    return this.request<WorkspaceInfo>("GET", "/v1/workspace");
  }

  /**
   * Check server health.
   * Wraps `GET /health` (unauthenticated on most deployments).
   */
  async health(): Promise<{ status: string; mutation_auth: string; read_auth: string }> {
    return this.request<{ status: string; mutation_auth: string; read_auth: string }>(
      "GET",
      "/health"
    );
  }

  /** The default releaseId this client was constructed with. */
  get defaultReleaseId(): string {
    return this.releaseId;
  }
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class FlightDeckError extends Error {
  /** HTTP status code; 0 for network-level failures. */
  readonly statusCode: number;
  /** Parsed response body from the server, if available. */
  readonly detail: unknown;
  /** Request-Id sent with the failing request (useful for server-side tracing). */
  readonly requestId: string;

  constructor(message: string, statusCode: number, detail: unknown, requestId: string) {
    super(message);
    this.name = "FlightDeckError";
    this.statusCode = statusCode;
    this.detail = detail;
    this.requestId = requestId;
  }
}
