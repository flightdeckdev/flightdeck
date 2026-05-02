import { useCallback, useEffect, useState } from "react";
import type { ReleaseRow, RunsListPayload } from "../api";
import { fetchRuns, fetchRunsExportBlob, loadTimeline } from "../api";
import { JsonPanel } from "../components/JsonPanel";

function shortId(id: string, keepStart = 12, keepEnd = 6) {
  if (id.length <= keepStart + keepEnd + 1) return id;
  return `${id.slice(0, keepStart)}…${id.slice(-keepEnd)}`;
}

export function RunsPage() {
  const [releases, setReleases] = useState<ReleaseRow[]>([]);
  const [releaseId, setReleaseId] = useState("");
  const [windowVal, setWindowVal] = useState("7d");
  const [environment, setEnvironment] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [traceId, setTraceId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [spanId, setSpanId] = useState("");
  const [offset, setOffset] = useState("0");
  const [limit, setLimit] = useState("50");

  const [result, setResult] = useState<RunsListPayload | null>(null);
  const [rawErr, setRawErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);

  useEffect(() => {
    void loadTimeline()
      .then((tl) => setReleases(tl.releases))
      .catch(() => {
        /* optional */
      });
  }, []);

  const runQuery = useCallback(async () => {
    setRawErr(null);
    setResult(null);
    const rid = releaseId.trim();
    if (!rid) {
      setRawErr("Release ID is required.");
      return;
    }
    const off = Number.parseInt(offset, 10);
    const lim = Number.parseInt(limit, 10);
    if (!Number.isFinite(off) || off < 0) {
      setRawErr("Offset must be a non-negative integer.");
      return;
    }
    if (!Number.isFinite(lim) || lim < 1 || lim > 500) {
      setRawErr("Limit must be between 1 and 500.");
      return;
    }
    setBusy(true);
    try {
      const data = await fetchRuns({
        release_id: rid,
        window: windowVal.trim() || "7d",
        environment: environment.trim() || undefined,
        tenant_id: tenantId.trim() || undefined,
        task_id: taskId.trim() || undefined,
        trace_id: traceId.trim() || undefined,
        session_id: sessionId.trim() || undefined,
        span_id: spanId.trim() || undefined,
        offset: off,
        limit: lim,
      });
      setResult(data);
    } catch (e) {
      setRawErr(String(e));
    } finally {
      setBusy(false);
    }
  }, [
    environment,
    limit,
    offset,
    releaseId,
    sessionId,
    spanId,
    taskId,
    tenantId,
    traceId,
    windowVal,
  ]);

  const downloadExport = useCallback(async () => {
    setRawErr(null);
    const rid = releaseId.trim();
    if (!rid) {
      setRawErr("Release ID is required.");
      return;
    }
    const off = Number.parseInt(offset, 10);
    const lim = Number.parseInt(limit, 10);
    if (!Number.isFinite(off) || off < 0 || !Number.isFinite(lim) || lim < 1 || lim > 500) {
      setRawErr("Offset and limit must be valid (limit 1–500).");
      return;
    }
    setExportBusy(true);
    try {
      const { blob } = await fetchRunsExportBlob({
        release_id: rid,
        window: windowVal.trim() || "7d",
        environment: environment.trim() || undefined,
        tenant_id: tenantId.trim() || undefined,
        task_id: taskId.trim() || undefined,
        trace_id: traceId.trim() || undefined,
        session_id: sessionId.trim() || undefined,
        span_id: spanId.trim() || undefined,
        offset: off,
        limit: lim,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `runs_${rid.slice(0, 20)}.ndjson`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setRawErr(String(e));
    } finally {
      setExportBusy(false);
    }
  }, [
    environment,
    limit,
    offset,
    releaseId,
    sessionId,
    spanId,
    taskId,
    tenantId,
    traceId,
    windowVal,
  ]);

  return (
    <>
      <div className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Run events</h2>
          <p className="fd-page-sub">
            Read-only slice of ingested runs (<code className="fd-mono fd-mono--sm">GET /v1/runs</code>). Newest
            first; offset pages through the match set.
          </p>
        </div>
      </div>

      <section className="fd-card">
        <div className="fd-card__head">
          <h3 className="fd-card__subtitle">Query</h3>
        </div>
        <div className="fd-form-grid">
          <label className="fd-field fd-field--full">
            <span className="fd-field__label">Release ID</span>
            <input
              className="fd-input"
              value={releaseId}
              onChange={(e) => setReleaseId(e.target.value)}
              list="fd-release-ids"
            />
            <datalist id="fd-release-ids">
              {releases.map((r) => (
                <option key={r.release_id} value={r.release_id}>
                  {r.agent_id} v{r.version}
                </option>
              ))}
            </datalist>
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Window</span>
            <input className="fd-input" value={windowVal} onChange={(e) => setWindowVal(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Environment (optional)</span>
            <input className="fd-input" value={environment} onChange={(e) => setEnvironment(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Tenant (optional)</span>
            <input className="fd-input" value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Task (optional)</span>
            <input className="fd-input" value={taskId} onChange={(e) => setTaskId(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Trace ID (optional)</span>
            <input className="fd-input" value={traceId} onChange={(e) => setTraceId(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Session ID (optional)</span>
            <input className="fd-input" value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Span ID (optional)</span>
            <input className="fd-input" value={spanId} onChange={(e) => setSpanId(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Offset</span>
            <input className="fd-input" value={offset} onChange={(e) => setOffset(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Limit (1–500)</span>
            <input className="fd-input" value={limit} onChange={(e) => setLimit(e.target.value)} />
          </label>
        </div>
        <div className="fd-actions">
          <button type="button" className="fd-btn fd-btn--primary" disabled={busy} onClick={() => void runQuery()}>
            {busy ? "Loading…" : "Load runs"}
          </button>
          <button
            type="button"
            className="fd-btn fd-btn--ghost"
            disabled={exportBusy}
            onClick={() => void downloadExport()}
          >
            {exportBusy ? "Exporting…" : "Download NDJSON"}
          </button>
        </div>
        {rawErr ? <p className="fd-alert fd-alert--error">{rawErr}</p> : null}
      </section>

      {result ? (
        <section className="fd-card" aria-label="Run events results">
          <div className="fd-card__head">
            <h3 className="fd-card__subtitle">Results</h3>
            <p className="fd-card__desc">
              matched_total={result.matched_total} returned={result.returned} truncated=
              {String(result.truncated)} offset={result.offset}
            </p>
          </div>
          <div className="fd-table-wrap">
            <table className="fd-table">
              <thead>
                <tr>
                  <th scope="col">Run ID</th>
                  <th scope="col">Timestamp</th>
                  <th scope="col">Agent</th>
                </tr>
              </thead>
              <tbody>
                {result.events.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="fd-muted">
                      No events in this page.
                    </td>
                  </tr>
                ) : (
                  result.events.map((ev, idx) => {
                    const runId = typeof ev.run_id === "string" ? ev.run_id : "";
                    const ts = typeof ev.timestamp === "string" ? ev.timestamp : "";
                    const agent = typeof ev.agent_id === "string" ? ev.agent_id : "";
                    return (
                      <tr key={`${runId}-${idx}`}>
                        <td className="fd-mono">{shortId(runId)}</td>
                        <td className="fd-mono">{ts}</td>
                        <td>{agent}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <JsonPanel title="Raw JSON" value={JSON.stringify(result, null, 2)} defaultOpen={false} />
        </section>
      ) : null}
    </>
  );
}
