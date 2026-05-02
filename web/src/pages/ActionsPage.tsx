import { useState } from "react";
import type { ActionOutcomePayload } from "../api";
import { fetchJson } from "../api";
import { Badge } from "../components/Badge";
import { JsonPanel } from "../components/JsonPanel";
import { useTimelineRefresh } from "../context/TimelineRefreshContext";

function shortId(id: string, keepStart = 10, keepEnd = 6) {
  if (id.length <= keepStart + keepEnd + 1) return id;
  return `${id.slice(0, keepStart)}…${id.slice(-keepEnd)}`;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

/**
 * Coerces `/v1/promote` and `/v1/rollback` 200 responses into an
 * `ActionOutcomePayload`.  Returns null for anything that doesn't look like
 * the documented contract so we can fall back to the raw JSON panel.
 */
function pickOutcome(data: unknown): ActionOutcomePayload | null {
  if (!isRecord(data)) return null;
  const policy = data.policy;
  if (!isRecord(policy)) return null;
  const reasons = Array.isArray(policy.reasons)
    ? policy.reasons.filter((r): r is string => typeof r === "string")
    : [];
  if (
    typeof data.action_id !== "string" ||
    typeof data.release_id !== "string" ||
    typeof data.agent_id !== "string" ||
    typeof data.environment !== "string" ||
    (data.action !== "promote" && data.action !== "rollback") ||
    typeof data.promoted_pointer_changed !== "boolean"
  ) {
    return null;
  }
  return {
    action_id: data.action_id,
    action: data.action,
    release_id: data.release_id,
    agent_id: data.agent_id,
    environment: data.environment,
    baseline_release_id:
      typeof data.baseline_release_id === "string" ? data.baseline_release_id : null,
    promoted_pointer_changed: data.promoted_pointer_changed,
    policy: {
      passed: policy.passed === true,
      reasons,
      evaluated_at: typeof policy.evaluated_at === "string" ? policy.evaluated_at : undefined,
    },
  };
}

export function ActionsPage() {
  const { notifyTimelineMutated } = useTimelineRefresh();
  const [actRelease, setActRelease] = useState("");
  const [actEnv, setActEnv] = useState("local");
  const [actWindow, setActWindow] = useState("7d");
  const [actReason, setActReason] = useState("");
  const [actOutcome, setActOutcome] = useState<ActionOutcomePayload | null>(null);
  const [actRaw, setActRaw] = useState<string | null>(null);
  const [actErr, setActErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "promote" | "rollback">(null);

  const runAction = async (path: "/v1/promote" | "/v1/rollback") => {
    setActErr(null);
    setActOutcome(null);
    setActRaw(null);
    const reason = actReason.trim();
    if (!reason) {
      setActErr("Reason is required.");
      return;
    }
    const label = path === "/v1/promote" ? "promote" : "rollback";
    if (!window.confirm(`Confirm ${label} for this release?`)) {
      return;
    }
    setBusy(path === "/v1/promote" ? "promote" : "rollback");
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
      setActOutcome(pickOutcome(data));
      setActRaw(JSON.stringify(data, null, 2));
      notifyTimelineMutated();
    } catch (e) {
      setActErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <div className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Promote & rollback</h2>
          <p className="fd-page-sub">
            Mutations use the same HTTP contract as the CLI. When{" "}
            <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code> is set, include it via{" "}
            <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code> for local dev.
          </p>
        </div>
      </div>

      <section className="fd-card">
        <div className="fd-form-grid">
          <label className="fd-field">
            <span className="fd-field__label">Release ID</span>
            <input className="fd-input" value={actRelease} onChange={(e) => setActRelease(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Environment</span>
            <input className="fd-input" value={actEnv} onChange={(e) => setActEnv(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Window</span>
            <input className="fd-input" value={actWindow} onChange={(e) => setActWindow(e.target.value)} />
          </label>
          <label className="fd-field fd-field--full">
            <span className="fd-field__label">Reason (required)</span>
            <input className="fd-input" value={actReason} onChange={(e) => setActReason(e.target.value)} />
          </label>
        </div>
        <div className="fd-actions">
          <button
            type="button"
            className="fd-btn fd-btn--primary"
            disabled={busy !== null}
            onClick={() => void runAction("/v1/promote")}
          >
            {busy === "promote" ? "Promoting…" : "Promote"}
          </button>
          <button
            type="button"
            className="fd-btn fd-btn--ghost"
            disabled={busy !== null}
            onClick={() => void runAction("/v1/rollback")}
          >
            {busy === "rollback" ? "Rolling back…" : "Rollback"}
          </button>
        </div>
      </section>

      {actErr ? <p className="fd-alert fd-alert--error">{actErr}</p> : null}

      {actOutcome ? (
        <section className="fd-card">
          <div className="fd-card__head">
            <h3 className="fd-card__subtitle">
              {actOutcome.action === "promote" ? "Promotion" : "Rollback"} outcome
            </h3>
            <div className="fd-inline">
              <span className="fd-muted">Policy:</span>{" "}
              <Badge tone={actOutcome.policy.passed ? "pass" : "fail"}>
                {actOutcome.policy.passed ? "PASS" : "FAIL"}
              </Badge>
            </div>
          </div>
          <p className="fd-muted fd-samples">
            Pointer:{" "}
            <Badge tone={actOutcome.promoted_pointer_changed ? "pass" : "neutral"}>
              {actOutcome.promoted_pointer_changed ? "Updated" : "Unchanged"}
            </Badge>{" "}
            · agent={actOutcome.agent_id} · env={actOutcome.environment}
          </p>
          <div className="fd-metric-grid">
            <div className="fd-metric">
              <div className="fd-metric__label">Action ID</div>
              <div className="fd-metric__row">
                <code className="fd-mono fd-mono--sm" title={actOutcome.action_id}>
                  {shortId(actOutcome.action_id)}
                </code>
              </div>
            </div>
            <div className="fd-metric">
              <div className="fd-metric__label">Release</div>
              <div className="fd-metric__row">
                <code className="fd-mono fd-mono--sm" title={actOutcome.release_id}>
                  {shortId(actOutcome.release_id)}
                </code>
              </div>
            </div>
            <div className="fd-metric">
              <div className="fd-metric__label">Previous baseline</div>
              <div className="fd-metric__row">
                {actOutcome.baseline_release_id ? (
                  <code
                    className="fd-mono fd-mono--sm"
                    title={actOutcome.baseline_release_id}
                  >
                    {shortId(actOutcome.baseline_release_id)}
                  </code>
                ) : (
                  <span className="fd-muted">none (first promotion)</span>
                )}
              </div>
            </div>
          </div>
          {actOutcome.policy.reasons.length > 0 ? (
            <ul className="fd-reasons">
              {actOutcome.policy.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {actRaw ? (
        <JsonPanel title="Raw response JSON" value={actRaw} defaultOpen={actOutcome === null} />
      ) : null}
    </>
  );
}
