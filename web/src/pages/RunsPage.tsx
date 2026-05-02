import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { ReleaseRow, RunsListPayload } from "../api";
import { fetchRuns, fetchRunsExportBlob, loadTimeline } from "../api";
import { JsonPanel } from "../components/JsonPanel";

function shortId(id: string, keepStart = 12, keepEnd = 6) {
  if (id.length <= keepStart + keepEnd + 1) return id;
  return `${id.slice(0, keepStart)}…${id.slice(-keepEnd)}`;
}

function asRecord(v: unknown): Record<string, unknown> | null {
  if (v && typeof v === "object" && !Array.isArray(v)) return v as Record<string, unknown>;
  return null;
}

function getRequest(ev: Record<string, unknown>): Record<string, unknown> | null {
  return asRecord(ev.request);
}

function getMetrics(ev: Record<string, unknown>): Record<string, unknown> | null {
  return asRecord(ev.metrics);
}

function getTraceId(ev: Record<string, unknown>): string {
  const req = getRequest(ev);
  const t = req?.trace_id;
  return typeof t === "string" ? t : "";
}

function getLatencyMs(ev: Record<string, unknown>): number | null {
  const m = getMetrics(ev);
  const n = m?.latency_ms;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

function getSuccess(ev: Record<string, unknown>): boolean {
  const m = getMetrics(ev);
  const s = m?.success;
  return s !== false;
}

/** Preserves API order (newest first); one group per distinct trace_id (or a single "no trace" bucket). */
function buildTraceGroups(events: unknown[]): { key: string; rows: Record<string, unknown>[] }[] {
  const order: string[] = [];
  const map = new Map<string, Record<string, unknown>[]>();
  for (const ev of events) {
    const rec = ev as Record<string, unknown>;
    const tid = getTraceId(rec);
    const key = tid || "__none__";
    if (!map.has(key)) {
      map.set(key, []);
      order.push(key);
    }
    map.get(key)!.push(rec);
  }
  return order.map((key) => ({ key, rows: map.get(key)! }));
}

export function RunsPage() {
  const drawerTitleId = useId();
  const closeBtnRef = useRef<HTMLButtonElement>(null);

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
  const [detailEvent, setDetailEvent] = useState<Record<string, unknown> | null>(null);
  const [groupByTrace, setGroupByTrace] = useState(false);

  useEffect(() => {
    void loadTimeline()
      .then((tl) => setReleases(tl.releases))
      .catch(() => {
        /* optional */
      });
  }, []);

  useEffect(() => {
    if (!detailEvent) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDetailEvent(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [detailEvent]);

  useEffect(() => {
    if (!detailEvent) return;
    const t = window.setTimeout(() => closeBtnRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [detailEvent]);

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

  const closeDrawer = useCallback(() => setDetailEvent(null), []);

  const renderEventRow = useCallback(
    (rec: Record<string, unknown>, idx: number, keyPrefix: string) => {
      const runId = typeof rec.run_id === "string" ? rec.run_id : "";
      const ts = typeof rec.timestamp === "string" ? rec.timestamp : "";
      const agent = typeof rec.agent_id === "string" ? rec.agent_id : "";
      const tid = getTraceId(rec);
      const lat = getLatencyMs(rec);
      const ok = getSuccess(rec);
      return (
        <tr key={`${keyPrefix}-${runId}-${idx}`}>
          <td className="fd-mono">{shortId(runId)}</td>
          <td className="fd-mono fd-nowrap">{ts}</td>
          <td>{agent}</td>
          <td className="fd-mono fd-mono--sm">{tid ? shortId(tid, 8, 4) : "—"}</td>
          <td>
            <span className={`fd-badge ${ok ? "fd-badge--pass" : "fd-badge--fail"}`}>
              {ok ? "ok" : "err"}
            </span>
            {lat != null ? (
              <span className="fd-muted" style={{ marginLeft: "0.35rem", fontSize: "0.78rem" }}>
                {lat}ms
              </span>
            ) : null}
          </td>
          <td>
            <button
              type="button"
              className="fd-btn fd-btn--ghost fd-btn--sm"
              aria-haspopup="dialog"
              onClick={() => setDetailEvent(rec)}
            >
              View
            </button>
          </td>
        </tr>
      );
    },
    [],
  );

  const tableHead = (
    <thead>
      <tr>
        <th scope="col">Run ID</th>
        <th scope="col">Timestamp</th>
        <th scope="col">Agent</th>
        <th scope="col">Trace</th>
        <th scope="col">Status</th>
        <th scope="col">
          <span className="fd-sr-only">Actions</span>
        </th>
      </tr>
    </thead>
  );

  return (
    <>
      <div className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Run events</h2>
          <p className="fd-page-sub">
            Read-only slice of ingested runs (<code className="fd-mono fd-mono--sm">GET /v1/runs</code>). Newest
            first; offset pages through the match set. Use a row&apos;s <strong>View</strong> action for structured
            detail (same payload as export lines).
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
        <p className="fd-inline fd-muted" style={{ marginTop: "0.75rem" }}>
          <strong>Export</strong> uses the same filters and <strong>limit</strong> as this form (server cap 500 rows
          per download). Truncation warnings apply to the returned page, not necessarily the whole ledger.
        </p>
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
        <section className="fd-card" aria-label="Run events results" aria-busy={busy}>
          <div className="fd-card__head fd-card__head--row">
            <div>
              <h3 className="fd-card__subtitle">Results</h3>
              <p className="fd-card__desc">
                matched_total={result.matched_total} returned={result.returned} truncated=
                {String(result.truncated)} offset={result.offset}
              </p>
            </div>
            <label className="fd-checkbox-label">
              <input
                type="checkbox"
                checked={groupByTrace}
                onChange={(e) => setGroupByTrace(e.target.checked)}
              />
              <span>Group by trace_id</span>
            </label>
          </div>

          {result.matched_total === 0 ? (
            <div className="fd-empty-state" role="status">
              <p className="fd-empty-state__title">No run events matched</p>
              <p className="fd-empty-state__body">
                Nothing in this release matched the time window and filters. Try a wider <strong>Window</strong>,
                clear optional filters, or confirm events were ingested for this <strong>Release ID</strong>.
              </p>
            </div>
          ) : null}

          {result.matched_total > 0 && result.returned === 0 ? (
            <p className="fd-alert fd-alert--info" role="status">
              This page is empty: <strong>offset</strong> is past the end of the match set. Lower offset or increase
              limit.
            </p>
          ) : null}

          {result.truncated ? (
            <p className="fd-alert fd-alert--warn" role="status">
              More events match this query than fit in this page. Increase <strong>offset</strong> to page forward, or
              narrow filters (for example <strong>Trace ID</strong>) to shrink the match set.
            </p>
          ) : null}

          {result.matched_total > 0 ? (
            groupByTrace ? (
              <div className="fd-trace-groups">
                {result.events.length === 0 ? (
                  <p className="fd-muted">No events in this page.</p>
                ) : (
                  buildTraceGroups(result.events).map((g) => (
                    <details key={g.key} className="fd-trace-group" open>
                      <summary className="fd-trace-group__summary">
                        {g.key === "__none__" ? (
                          <span>
                            <strong>No trace_id</strong>
                            <span className="fd-muted"> · {g.rows.length} event(s)</span>
                          </span>
                        ) : (
                          <span>
                            <span className="fd-table__trace-sep-label">Trace</span>{" "}
                            <code className="fd-mono fd-mono--sm">{shortId(g.key, 18, 10)}</code>
                            <span className="fd-muted"> · {g.rows.length} event(s)</span>
                          </span>
                        )}
                      </summary>
                      <div className="fd-table-wrap">
                        <table className="fd-table">
                          {tableHead}
                          <tbody>{g.rows.map((rec, idx) => renderEventRow(rec, idx, g.key))}</tbody>
                        </table>
                      </div>
                    </details>
                  ))
                )}
              </div>
            ) : (
              <div className="fd-table-wrap">
                <table className="fd-table">
                  {tableHead}
                  <tbody>
                    {result.events.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="fd-empty-cell">
                          No events in this page.
                        </td>
                      </tr>
                    ) : (
                      (() => {
                        const rows: ReactNode[] = [];
                        let prevTrace: string | null = null;
                        result.events.forEach((ev, idx) => {
                          const rec = ev as Record<string, unknown>;
                          const tid = getTraceId(rec);
                          if (tid && tid !== prevTrace) {
                            rows.push(
                              <tr key={`trace-sep-${idx}-${tid}`} className="fd-table__trace-sep">
                                <td colSpan={6}>
                                  <span className="fd-table__trace-sep-label">Trace</span>{" "}
                                  <code className="fd-mono fd-mono--sm">{shortId(tid, 18, 10)}</code>
                                </td>
                              </tr>,
                            );
                            prevTrace = tid;
                          }
                          rows.push(renderEventRow(rec, idx, "flat"));
                        });
                        return rows;
                      })()
                    )}
                  </tbody>
                </table>
              </div>
            )
          ) : null}

          <JsonPanel title="Raw JSON (page)" value={JSON.stringify(result, null, 2)} defaultOpen={false} />
        </section>
      ) : (
        <section className="fd-card fd-card--hint" aria-label="Getting started">
          <p className="fd-empty" style={{ margin: 0 }}>
            Choose a <strong>Release ID</strong> (datalist is filled from registered releases when the server is
            reachable), then <strong>Load runs</strong> to query <code className="fd-mono fd-mono--sm">GET /v1/runs</code>
            .
          </p>
        </section>
      )}

      {detailEvent ? (
        <div className="fd-drawer-root" role="presentation">
          <button
            type="button"
            className="fd-drawer-backdrop"
            aria-label="Close run detail"
            onClick={closeDrawer}
          />
          <aside
            className="fd-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby={drawerTitleId}
          >
            <div className="fd-drawer__head">
              <h3 className="fd-drawer__title" id={drawerTitleId}>
                Run event
              </h3>
              <button ref={closeBtnRef} type="button" className="fd-btn fd-btn--ghost" onClick={closeDrawer}>
                Close
              </button>
            </div>
            <div className="fd-drawer__body">
              {(() => {
                const runId = typeof detailEvent.run_id === "string" ? detailEvent.run_id : "";
                const ts = typeof detailEvent.timestamp === "string" ? detailEvent.timestamp : "";
                const agent = typeof detailEvent.agent_id === "string" ? detailEvent.agent_id : "";
                const tid = getTraceId(detailEvent);
                const sess = getRequest(detailEvent)?.session_id;
                const span = getRequest(detailEvent)?.span_id;
                const lat = getLatencyMs(detailEvent);
                const ok = getSuccess(detailEvent);
                const err = getMetrics(detailEvent)?.error_type;
                return (
                  <dl className="fd-dl">
                    <div>
                      <dt>run_id</dt>
                      <dd className="fd-mono fd-mono--sm">{runId || "—"}</dd>
                    </div>
                    <div>
                      <dt>timestamp</dt>
                      <dd className="fd-mono fd-mono--sm">{ts || "—"}</dd>
                    </div>
                    <div>
                      <dt>agent_id</dt>
                      <dd>{agent || "—"}</dd>
                    </div>
                    <div>
                      <dt>trace_id</dt>
                      <dd className="fd-mono fd-mono--sm">{tid || "—"}</dd>
                    </div>
                    <div>
                      <dt>session_id</dt>
                      <dd className="fd-mono fd-mono--sm">{typeof sess === "string" ? sess : "—"}</dd>
                    </div>
                    <div>
                      <dt>span_id</dt>
                      <dd className="fd-mono fd-mono--sm">{typeof span === "string" ? span : "—"}</dd>
                    </div>
                    <div>
                      <dt>metrics</dt>
                      <dd>
                        <span className={`fd-badge ${ok ? "fd-badge--pass" : "fd-badge--fail"}`}>
                          {ok ? "success" : "failed"}
                        </span>
                        {lat != null ? <span className="fd-muted"> · {lat}ms</span> : null}
                        {typeof err === "string" && err ? (
                          <span className="fd-muted"> · error_type: {err}</span>
                        ) : null}
                      </dd>
                    </div>
                  </dl>
                );
              })()}
              <JsonPanel title="Full event JSON" value={JSON.stringify(detailEvent, null, 2)} defaultOpen />
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
