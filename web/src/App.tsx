import { useCallback, useEffect, useState } from "react";

type ReleaseRow = {
  release_id: string;
  agent_id: string;
  version: string;
  environment: string;
  checksum: string;
  created_at: string;
};

type PromotedRow = {
  agent_id: string;
  environment: string;
  release_id: string;
};

type ActionRow = {
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

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
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

export function App() {
  const [timelineText, setTimelineText] = useState<string>("Loading…");
  const [diffBaseline, setDiffBaseline] = useState("");
  const [diffCandidate, setDiffCandidate] = useState("");
  const [diffWindow, setDiffWindow] = useState("7d");
  const [diffEnv, setDiffEnv] = useState("local");
  const [diffOut, setDiffOut] = useState("");

  const [actRelease, setActRelease] = useState("");
  const [actEnv, setActEnv] = useState("local");
  const [actWindow, setActWindow] = useState("7d");
  const [actReason, setActReason] = useState("");
  const [actOut, setActOut] = useState("");

  const refreshTimeline = useCallback(async () => {
    try {
      const [releases, promoted, actions] = await Promise.all([
        fetchJson<{ releases: ReleaseRow[] }>("/v1/releases"),
        fetchJson<{ promoted: PromotedRow[] }>("/v1/promoted"),
        fetchJson<{ actions: ActionRow[] }>("/v1/actions"),
      ]);
      setTimelineText(
        JSON.stringify(
          {
            releases: releases.releases,
            promoted: promoted.promoted,
            actions: actions.actions,
          },
          null,
          2,
        ),
      );
    } catch (e) {
      setTimelineText(String(e));
    }
  }, []);

  useEffect(() => {
    void refreshTimeline();
  }, [refreshTimeline]);

  const runDiff = async () => {
    setDiffOut("");
    try {
      const body = {
        baseline_release_id: diffBaseline.trim(),
        candidate_release_id: diffCandidate.trim(),
        window: diffWindow.trim(),
        environment: diffEnv.trim() || null,
      };
      const data = await fetchJson<unknown>("/v1/diff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setDiffOut(JSON.stringify(data, null, 2));
    } catch (e) {
      setDiffOut(String(e));
    }
  };

  const runAction = async (path: "/v1/promote" | "/v1/rollback") => {
    setActOut("");
    const reason = actReason.trim();
    if (!reason) {
      setActOut("Reason is required.");
      return;
    }
    const label = path === "/v1/promote" ? "promote" : "rollback";
    if (!window.confirm(`Confirm ${label} for this release?`)) {
      return;
    }
    try {
      const data = await fetchJson<unknown>(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          release_id: actRelease.trim(),
          environment: actEnv.trim(),
          window: actWindow.trim(),
          reason,
          actor: "react-ui",
        }),
      });
      setActOut(JSON.stringify(data, null, 2));
      await refreshTimeline();
    } catch (e) {
      setActOut(String(e));
    }
  };

  return (
    <>
      <h1>FlightDeck</h1>
      <p className="muted">Local timeline, diff, and promotion actions (React + Vite).</p>

      <section>
        <h2>Timeline</h2>
        <button type="button" onClick={() => void refreshTimeline()}>
          Refresh
        </button>
        <pre>{timelineText}</pre>
      </section>

      <section>
        <h2>Run diff</h2>
        <div>
          <label htmlFor="db">Baseline release</label>
          <input id="db" value={diffBaseline} onChange={(e) => setDiffBaseline(e.target.value)} />
        </div>
        <div>
          <label htmlFor="dc">Candidate release</label>
          <input id="dc" value={diffCandidate} onChange={(e) => setDiffCandidate(e.target.value)} />
        </div>
        <div>
          <label htmlFor="dw">Window</label>
          <input id="dw" value={diffWindow} onChange={(e) => setDiffWindow(e.target.value)} />
        </div>
        <div>
          <label htmlFor="de">Environment</label>
          <input id="de" value={diffEnv} onChange={(e) => setDiffEnv(e.target.value)} />
        </div>
        <button type="button" onClick={() => void runDiff()}>
          Compute diff
        </button>
        <pre>{diffOut}</pre>
      </section>

      <section>
        <h2>Promote / rollback</h2>
        <div>
          <label htmlFor="ar">Release id</label>
          <input id="ar" value={actRelease} onChange={(e) => setActRelease(e.target.value)} />
        </div>
        <div>
          <label htmlFor="ae">Environment</label>
          <input id="ae" value={actEnv} onChange={(e) => setActEnv(e.target.value)} />
        </div>
        <div>
          <label htmlFor="aw">Window</label>
          <input id="aw" value={actWindow} onChange={(e) => setActWindow(e.target.value)} />
        </div>
        <div>
          <label htmlFor="ar2">Reason</label>
          <input id="ar2" value={actReason} onChange={(e) => setActReason(e.target.value)} />
        </div>
        <button type="button" onClick={() => void runAction("/v1/promote")}>
          Promote
        </button>
        <button type="button" onClick={() => void runAction("/v1/rollback")}>
          Rollback
        </button>
        <pre>{actOut}</pre>
      </section>
    </>
  );
}
