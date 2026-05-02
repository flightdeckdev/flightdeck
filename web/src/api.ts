export type ReleaseRow = {
  release_id: string;
  agent_id: string;
  version: string;
  environment: string;
  checksum: string;
  created_at: string;
};

export type PromotedRow = {
  agent_id: string;
  environment: string;
  release_id: string;
};

export type ActionRow = {
  action_id: string;
  action: string;
  release_id: string;
  agent_id: string;
  environment: string;
  baseline_release_id: string | null;
  reason: string;
  policy_passed: boolean;
  policy_reasons: string[];
  created_at: string;
  audit_seq: number | null;
};

export type TimelinePayload = {
  releases: ReleaseRow[];
  promoted: PromotedRow[];
  actions: ActionRow[];
};

export type HealthPayload = {
  status: string;
  /** Present on current servers; `bearer` when `FLIGHTDECK_LOCAL_API_TOKEN` is set. */
  mutation_auth?: "bearer" | "loopback";
};

/**
 * Response shape for `GET /v1/metrics`. Mirrors `routes/metrics.py` and
 * `Storage.get_ledger_counters()`. Counters are non-negative integers; the
 * `actions_by_action` map is keyed by action name (e.g. `promote`, `rollback`).
 */
export type MetricsPayload = {
  counters: {
    releases_total: number;
    pricing_tables_total: number;
    run_events_total: number;
    promoted_pointers_total: number;
    actions_total: number;
    actions_by_action: Record<string, number>;
  };
  schema_version: number;
  generated_at: string;
};

export type PolicyResultPayload = {
  passed: boolean;
  reasons: string[];
  evaluated_at?: string;
};

/**
 * Response shape for `POST /v1/promote` and `POST /v1/rollback` (HTTP 200).
 * Mirrors `_action_body()` in `src/flightdeck/server/routes/actions.py`.
 *
 * On policy block, the server returns HTTP 409 with `{ detail: { message, outcome } }`
 * where `outcome` matches this shape.
 */
export type ActionOutcomePayload = {
  action_id: string;
  action: "promote" | "rollback";
  release_id: string;
  agent_id: string;
  environment: string;
  baseline_release_id: string | null;
  promoted_pointer_changed: boolean;
  policy: PolicyResultPayload;
};

function formatHttpErrorBody(data: unknown): string {
  if (typeof data !== "object" || data === null) {
    try {
      return JSON.stringify(data);
    } catch {
      return String(data);
    }
  }
  if (!("detail" in data)) {
    try {
      return JSON.stringify(data);
    } catch {
      return String(data);
    }
  }
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        try {
          return JSON.stringify(item);
        } catch {
          return String(item);
        }
      })
      .join("; ");
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const m = (detail as { message: unknown }).message;
    if (typeof m === "string") return m;
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = import.meta.env.VITE_FLIGHTDECK_LOCAL_API_TOKEN;
  if (typeof token === "string" && token.trim().length > 0 && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token.trim()}`);
  }
  const res = await fetch(path, { ...init, headers });
  const data: unknown = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = formatHttpErrorBody(data);
    throw new Error(message || `HTTP ${res.status}`);
  }
  return data as T;
}

/** `GET /v1/workspace` — read-only flags (see `schemas/v1/workspace_public.schema.json`). */
export type WorkspacePublicPayload = {
  api_version: string;
  kind: "WorkspacePublic";
  promotion_requires_approval: boolean;
  pricing_catalog_configured: boolean;
  server_version: string;
};

export type PromotionRequestListItem = {
  request_id: string;
  status: string;
  release_id: string;
  agent_id: string;
  environment: string;
  window: string;
  reason: string;
  actor: string;
  baseline_release_id: string | null;
  policy: PolicyResultPayload;
  created_at: string;
  resolved_at: string | null;
  completed_action_id: string | null;
};

export async function fetchWorkspace(): Promise<WorkspacePublicPayload> {
  return fetchJson<WorkspacePublicPayload>("/v1/workspace");
}

export async function fetchPromotionRequests(params?: {
  status?: string;
  limit?: number;
}): Promise<{ requests: PromotionRequestListItem[] }> {
  const sp = new URLSearchParams();
  if (params?.status) sp.set("status", params.status);
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const q = sp.toString();
  return fetchJson<{ requests: PromotionRequestListItem[] }>(
    `/v1/promotion-requests${q ? `?${q}` : ""}`,
  );
}

export async function fetchHealth(): Promise<HealthPayload> {
  return fetchJson<HealthPayload>("/health");
}

export async function fetchMetrics(): Promise<MetricsPayload> {
  return fetchJson<MetricsPayload>("/v1/metrics");
}

/** Response shape for `GET /v1/runs` (see `query_run_events_page` on the server). */
export type RunsListPayload = {
  release_id: string;
  since: string;
  until: string;
  filters: Record<string, unknown>;
  offset: number;
  limit: number;
  matched_total: number;
  returned: number;
  truncated: boolean;
  events: Record<string, unknown>[];
};

export async function fetchRuns(params: {
  release_id: string;
  window: string;
  environment?: string;
  tenant_id?: string;
  task_id?: string;
  trace_id?: string;
  session_id?: string;
  span_id?: string;
  offset?: number;
  limit?: number;
}): Promise<RunsListPayload> {
  const sp = new URLSearchParams();
  sp.set("release_id", params.release_id);
  sp.set("window", params.window);
  if (params.environment != null && params.environment !== "") sp.set("environment", params.environment);
  if (params.tenant_id != null && params.tenant_id !== "") sp.set("tenant_id", params.tenant_id);
  if (params.task_id != null && params.task_id !== "") sp.set("task_id", params.task_id);
  if (params.trace_id != null && params.trace_id !== "") sp.set("trace_id", params.trace_id);
  if (params.session_id != null && params.session_id !== "") sp.set("session_id", params.session_id);
  if (params.span_id != null && params.span_id !== "") sp.set("span_id", params.span_id);
  if (params.offset != null) sp.set("offset", String(params.offset));
  sp.set("limit", String(params.limit ?? 100));
  return fetchJson<RunsListPayload>(`/v1/runs?${sp.toString()}`);
}

/** `GET /v1/runs/export` — NDJSON body (read tier; same query params as `fetchRuns`). */
export async function fetchRunsExportBlob(params: {
  release_id: string;
  window: string;
  environment?: string;
  tenant_id?: string;
  task_id?: string;
  trace_id?: string;
  session_id?: string;
  span_id?: string;
  offset?: number;
  limit?: number;
}): Promise<{ blob: Blob }> {
  const sp = new URLSearchParams();
  sp.set("release_id", params.release_id);
  sp.set("window", params.window);
  if (params.environment != null && params.environment !== "") sp.set("environment", params.environment);
  if (params.tenant_id != null && params.tenant_id !== "") sp.set("tenant_id", params.tenant_id);
  if (params.task_id != null && params.task_id !== "") sp.set("task_id", params.task_id);
  if (params.trace_id != null && params.trace_id !== "") sp.set("trace_id", params.trace_id);
  if (params.session_id != null && params.session_id !== "") sp.set("session_id", params.session_id);
  if (params.span_id != null && params.span_id !== "") sp.set("span_id", params.span_id);
  if (params.offset != null) sp.set("offset", String(params.offset));
  sp.set("limit", String(params.limit ?? 500));
  const headers = new Headers();
  const token = import.meta.env.VITE_FLIGHTDECK_LOCAL_API_TOKEN;
  if (typeof token === "string" && token.trim().length > 0 && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token.trim()}`);
  }
  const res = await fetch(`/v1/runs/export?${sp.toString()}`, { headers });
  const text = await res.text();
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "string") msg = j.detail;
    } catch {
      if (text.trim()) msg = text.slice(0, 500);
    }
    throw new Error(msg);
  }
  return { blob: new Blob([text], { type: "application/x-ndjson" }) };
}

export async function loadTimeline(): Promise<TimelinePayload> {
  const [releases, promoted, actions] = await Promise.all([
    fetchJson<{ releases: ReleaseRow[] }>("/v1/releases"),
    fetchJson<{ promoted: PromotedRow[] }>("/v1/promoted"),
    fetchJson<{ actions: ActionRow[] }>("/v1/actions"),
  ]);
  return {
    releases: releases.releases,
    promoted: promoted.promoted,
    actions: actions.actions,
  };
}
