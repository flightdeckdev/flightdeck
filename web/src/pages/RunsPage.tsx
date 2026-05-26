import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ReleaseRow, RunsListPayload } from "../api";
import { fetchRuns, fetchRunsExportBlob, loadTimeline } from "../api";
import { Button } from "../components/Button";
import { JsonPanel } from "../components/JsonPanel";
import { pickTrimmedSearch } from "../urlSearch";
import { useDocumentTitle } from "../useDocumentTitle";

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

function getSessionId(ev: Record<string, unknown>): string {
  const req = getRequest(ev);
  const v = req?.session_id;
  return typeof v === "string" ? v : "";
}

function getSpanId(ev: Record<string, unknown>): string {
  const req = getRequest(ev);
  const v = req?.span_id;
  return typeof v === "string" ? v : "";
}

type RunsQueryErrorKind = "network" | "client" | "server" | "unknown";

function classifyRunsFetchError(e: unknown): { kind: RunsQueryErrorKind; title: string; detail: string } {
  const detail = e instanceof Error ? e.message : String(e);
  const lower = detail.toLowerCase();
  if (
    e instanceof TypeError ||
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("load failed") ||
    lower.includes("network request failed")
  ) {
    return {
      kind: "network",
      title: "Could not reach the server",
      detail: detail || "Check your connection, VPN, and that FlightDeck is running.",
    };
  }
  const httpMatch = detail.match(/HTTP\s+(\d{3})\b/i);
  if (httpMatch) {
    const code = Number.parseInt(httpMatch[1], 10);
    if (code >= 500) {
      return { kind: "server", title: `Server error (${code})`, detail };
    }
    if (code >= 400) {
      return { kind: "client", title: `Request rejected (${code})`, detail };
    }
  }
  return { kind: "unknown", title: "Run query failed", detail };
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
  useDocumentTitle("Run events");
  const drawerTitleId = useId();
  const [searchParams] = useSearchParams();
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const drawerPanelRef = useRef<HTMLDivElement>(null);
  const drawerReturnFocusRef = useRef<HTMLElement | null>(null);

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
  const [runsQueryError, setRunsQueryError] = useState<{
    kind: RunsQueryErrorKind;
    title: string;
    detail: string;
  } | null>(null);
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
    const rid = pickTrimmedSearch(searchParams, "release_id");
    const win = pickTrimmedSearch(searchParams, "window");
    const env = pickTrimmedSearch(searchParams, "environment");
    if (rid) setReleaseId(rid);
    if (win) setWindowVal(win);
    setEnvironment(env);
  }, [searchParams]);

  const closeDrawer = useCallback(() => {
    setDetailEvent(null);
    window.setTimeout(() => {
      drawerReturnFocusRef.current?.focus();
      drawerReturnFocusRef.current = null;
    }, 0);
  }, []);

  useEffect(() => {
    if (!detailEvent) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeDrawer();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [detailEvent, closeDrawer]);

  useEffect(() => {
    if (!detailEvent) return;
    const t = window.setTimeout(() => closeBtnRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [detailEvent]);

  useEffect(() => {
    if (!detailEvent) return;
    const drawer = drawerPanelRef.current;
    if (!drawer) return;

    const selector =
      'a[href]:not([tabindex="-1"]), button:not([disabled]):not([tabindex="-1"]), textarea:not([disabled]):not([tabindex="-1"]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled]):not([tabindex="-1"]), [tabindex]:not([tabindex="-1"])';

    const focusables = (): HTMLElement[] =>
      Array.from(drawer.querySelectorAll<HTMLElement>(selector)).filter(
        (el) => !el.hasAttribute("disabled") && el.tabIndex !== -1,
      );

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const nodes = focusables();
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (active === first || !drawer.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [detailEvent]);

  const runQuery = useCallback(async () => {
    setRawErr(null);
    setRunsQueryError(null);
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
      setRunsQueryError(null);
    } catch (e) {
      setRunsQueryError(classifyRunsFetchError(e));
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
            {lat != null ? <span className="fd-muted-xs fd-ml-sm">{lat}ms</span> : null}
          </td>
          <td>
            <button
              type="button"
              className="fd-btn fd-btn--ghost fd-btn--sm"
              aria-haspopup="dialog"
              aria-label={`View run details for ${shortId(runId, 14, 8)}`}
              onClick={(e) => {
                drawerReturnFocusRef.current = e.currentTarget;
                setDetailEvent(rec);
              }}
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
      <header className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Run events</h2>
          <p className="fd-page-sub fd-page-sub--tight">
            <strong>What changed?</strong> Inspect ingested runs for a release. <strong>Is it safe?</strong> Correlate with{" "}
            <Link to="/diff">Diff</Link> policy. <strong>Can I ship?</strong> Evidence supports the promotion decision on{" "}
            <Link to="/actions">Actions</Link>.
          </p>
          <p className="fd-page-sub fd-page-sub--meta">
            Read-only <code className="fd-mono fd-mono--sm">GET /v1/runs</code>, newest first; paste a release ID from{" "}
            <Link to="/">Overview</Link> or the CLI. Row <strong>View</strong> opens structured detail (same shape as export lines).
          </p>
        </div>
      </header>

      <section className="fd-card">
        <div className="fd-card__head">
          <h3 className="fd-card__subtitle">Query</h3>
        </div>
        <div className="fd-form-grid">
          <label className="fd-field fd-field--full">
            <span className="fd-field__label">Release ID</span>
            <input
              className={`fd-input${rawErr === "Release ID is required." ? " fd-input--invalid" : ""}`}
              value={releaseId}
              onChange={(e) => {
                setReleaseId(e.target.value);
                if (rawErr === "Release ID is required.") setRawErr(null);
              }}
              list="fd-release-ids"
              aria-invalid={rawErr === "Release ID is required."}
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
        <p className="fd-inline fd-muted fd-mt-xl">
          <strong>Export</strong> uses the same filters and <strong>limit</strong> as this form (server cap 500 rows
          per download). Truncation warnings apply to the returned page, not necessarily the whole ledger.
        </p>
        <div className="fd-actions">
          <Button
            variant="primary"
            disabled={busy || exportBusy}
            loading={busy}
            loadingLabel="Loading…"
            onClick={() => void runQuery()}
          >
            Load runs
          </Button>
          <Button
            variant="ghost"
            disabled={busy || exportBusy}
            loading={exportBusy}
            loadingLabel="Exporting…"
            onClick={() => void downloadExport()}
          >
            Download NDJSON
          </Button>
        </div>
        {rawErr ? <p className="fd-alert fd-alert--error">{rawErr}</p> : null}
      </section>

      {runsQueryError && !result ? (
        <section className="fd-card" aria-label="Run query error" aria-live="polite">
          <div className="fd-card__head">
            <h3 className="fd-card__subtitle">Could not load runs</h3>
          </div>
          <div className="fd-empty-state" role="alert">
            <p className="fd-empty-state__title">{runsQueryError.title}</p>
            <p className="fd-empty-state__body">
              {runsQueryError.kind === "network" ? (
                <>
                  This usually means the UI lost contact with the FlightDeck server (offline, wrong host, or CORS).
                  Confirm <code className="fd-mono fd-mono--sm">flightdeck serve</code> is up and you are on the same
                  origin the UI expects.
                </>
              ) : runsQueryError.kind === "client" ? (
                <>
                  The server refused this query (validation, auth, or missing data). Adjust filters or release ID, or
                  check API credentials if your deployment requires them.
                </>
              ) : runsQueryError.kind === "server" ? (
                <>The server reported an internal error. Retry in a moment; if it persists, check server logs.</>
              ) : (
                <>Something went wrong while loading run events. Details appear below.</>
              )}
            </p>
            <p className="fd-muted fd-mono fd-mono--sm fd-break-word fd-mt-md">
              {runsQueryError.detail}
            </p>
            <div className="fd-actions fd-mt-1">
              <Button variant="primary" disabled={busy || exportBusy} loading={busy} loadingLabel="Retrying…" onClick={() => void runQuery()}>
                Retry
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      {result ? (
        <section className="fd-card" aria-label="Run events results" aria-busy={busy}>
          <div className="fd-card__head fd-card__head--row">
            <div>
              <h3 className="fd-card__subtitle">Results</h3>
              <p className="fd-card__desc fd-results-meta">
                matched_total={result.matched_total} · returned={result.returned} · truncated={String(result.truncated)}{" "}
                · offset={result.offset}
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
                        <table className="fd-table fd-table--hover fd-table--striped">
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
                <table className="fd-table fd-table--hover fd-table--striped">
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
      ) : runsQueryError ? null : (
        <section className="fd-card fd-card--hint" aria-label="Getting started">
          <p className="fd-empty fd-m-0">
            Choose a <strong>Release ID</strong> (datalist is filled from registered releases when the server is
            reachable), then <strong>Load runs</strong> to query <code className="fd-mono fd-mono--sm">GET /v1/runs</code>
            .
          </p>
        </section>
      )}

      {detailEvent ? (
        <div ref={drawerPanelRef} className="fd-drawer-root" role="presentation">
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
                const sid = getSessionId(detailEvent);
                const spid = getSpanId(detailEvent);
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
                      <dd className="fd-mono fd-mono--sm">{sid || "—"}</dd>
                    </div>
                    <div>
                      <dt>span_id</dt>
                      <dd className="fd-mono fd-mono--sm">{spid || "—"}</dd>
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
