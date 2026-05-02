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

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = import.meta.env.VITE_FLIGHTDECK_LOCAL_API_TOKEN;
  if (typeof token === "string" && token.trim().length > 0 && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token.trim()}`);
  }
  const res = await fetch(path, { ...init, headers });
  const data: unknown = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : JSON.stringify(data);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return data as T;
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
