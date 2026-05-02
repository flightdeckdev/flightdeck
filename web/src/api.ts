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
