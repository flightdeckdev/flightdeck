import { useState } from "react";
import { fetchJson } from "../api";
import { JsonPanel } from "../components/JsonPanel";
import { useTimelineRefresh } from "../context/TimelineRefreshContext";

export function ActionsPage() {
  const { notifyTimelineMutated } = useTimelineRefresh();
  const [actRelease, setActRelease] = useState("");
  const [actEnv, setActEnv] = useState("local");
  const [actWindow, setActWindow] = useState("7d");
  const [actReason, setActReason] = useState("");
  const [actOut, setActOut] = useState<string | null>(null);
  const [actErr, setActErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "promote" | "rollback">(null);

  const runAction = async (path: "/v1/promote" | "/v1/rollback") => {
    setActErr(null);
    setActOut(null);
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
      setActOut(JSON.stringify(data, null, 2));
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
      {actOut ? <JsonPanel title="Last response JSON" value={actOut} defaultOpen /> : null}
    </>
  );
}
