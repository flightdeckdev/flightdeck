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
