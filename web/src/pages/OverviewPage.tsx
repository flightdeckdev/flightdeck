import { useCallback, useEffect, useId, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ActionRow, MetricsPayload, PromotedRow, ReleaseRow, TimelinePayload } from "../api";
import { fetchMetrics, loadTimeline } from "../api";
import { useTimelineRefresh } from "../context/TimelineRefreshContext";
import { Badge } from "../components/Badge";
import { JsonPanel } from "../components/JsonPanel";

function shortId(id: string, keepStart = 10, keepEnd = 6) {
  if (id.length <= keepStart + keepEnd + 1) return id;
  return `${id.slice(0, keepStart)}…${id.slice(-keepEnd)}`;
}

function TableShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const hid = useId();
  return (
    <section className="fd-card" aria-labelledby={hid}>
      <div className="fd-card__head">
        <h2 className="fd-card__title" id={hid}>
          {title}
        </h2>
        {description ? <p className="fd-card__desc">{description}</p> : null}
      </div>
      <div className="fd-table-wrap">{children}</div>
    </section>
  );
}

export function OverviewPage() {
  const { generation } = useTimelineRefresh();
  const [data, setData] = useState<TimelinePayload | null>(null);
  const [metrics, setMetrics] = useState<MetricsPayload | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    setMetricsError(null);
    try {
      const [timeline, m] = await Promise.allSettled([loadTimeline(), fetchMetrics()]);
      if (timeline.status === "fulfilled") {
        setData(timeline.value);
      } else {
        setError(String(timeline.reason));
        setData(null);
      }
      if (m.status === "fulfilled") {
        setMetrics(m.value);
      } else {
        setMetricsError(String(m.reason));
        setMetrics(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [generation, refresh]);

  const raw =
    data === null
      ? error ?? ""
      : JSON.stringify(
          { releases: data.releases, promoted: data.promoted, actions: data.actions },
          null,
          2,
        );

  return (
    <>
      <div className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Overview</h2>
          <p className="fd-page-sub">Registered releases, promotion pointers, and recent ledger actions.</p>
        </div>
        <button type="button" className="fd-btn fd-btn--primary" disabled={loading} onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      {error && !loading ? <p className="fd-alert fd-alert--error">{error}</p> : null}
      {loading ? (
        <div className="fd-loading-panel" aria-busy="true" aria-live="polite">
          <span className="fd-sr-only">Loading overview</span>
          <span className="fd-skeleton fd-skeleton--w60" />
          <span className="fd-skeleton fd-skeleton--w75 fd-skeleton--mt" />
          <span className="fd-skeleton fd-skeleton--w40 fd-skeleton--mt" />
        </div>
      ) : null}

      {metrics ? (
        <section className="fd-card" aria-label="Ledger metrics">
          <div className="fd-card__head">
            <h2 className="fd-card__title">Ledger metrics</h2>
            <p className="fd-card__desc">
              Read-only counters from{" "}
              <code className="fd-mono fd-mono--sm">GET /v1/metrics</code> (schema v
              {metrics.schema_version}, generated{" "}
              {new Date(metrics.generated_at).toLocaleString()}).
            </p>
          </div>
          <div className="fd-metric-grid">
            <div className="fd-metric">
              <div className="fd-metric__label">Releases</div>
              <div className="fd-metric__row">
                <span className="fd-metric__bc">{metrics.counters.releases_total}</span>
              </div>
            </div>
            <div className="fd-metric">
              <div className="fd-metric__label">Pricing tables</div>
              <div className="fd-metric__row">
                <span className="fd-metric__bc">{metrics.counters.pricing_tables_total}</span>
              </div>
            </div>
            <div className="fd-metric">
              <div className="fd-metric__label">Run events</div>
              <div className="fd-metric__row">
                <span className="fd-metric__bc">{metrics.counters.run_events_total}</span>
              </div>
            </div>
            <div className="fd-metric">
              <div className="fd-metric__label">Promoted pointers</div>
              <div className="fd-metric__row">
                <span className="fd-metric__bc">{metrics.counters.promoted_pointers_total}</span>
              </div>
            </div>
            <div className="fd-metric">
              <div className="fd-metric__label">Actions</div>
              <div className="fd-metric__row">
                <span className="fd-metric__bc">{metrics.counters.actions_total}</span>
              </div>
              {Object.keys(metrics.counters.actions_by_action).length > 0 ? (
                <div className="fd-metric__delta">
                  {Object.entries(metrics.counters.actions_by_action)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([k, v]) => `${k}=${v}`)
                    .join(" · ")}
                </div>
              ) : null}
            </div>
          </div>
          <p className="fd-inline-nav">
            Next: open <Link to="/diff">Diff</Link> to compare releases, or <Link to="/runs">Runs</Link> for evidence
            forensics.
          </p>
        </section>
      ) : metricsError && !loading ? (
        <p className="fd-alert fd-alert--warn">Ledger metrics unavailable: {metricsError}</p>
      ) : null}

      {data ? (
        <>
          <TableShell title="Releases" description="Artifacts registered in this workspace.">
            <table className="fd-table">
              <thead>
                <tr>
                  <th scope="col">Release ID</th>
                  <th scope="col">Agent</th>
                  <th scope="col">Version</th>
                  <th scope="col">Environment</th>
                  <th scope="col">Checksum</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.releases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="fd-empty-cell">
                      No releases yet.
                    </td>
                  </tr>
                ) : (
                  data.releases.map((r: ReleaseRow) => (
                    <tr key={r.release_id}>
                      <td>
                        <code className="fd-mono" title={r.release_id}>
                          {shortId(r.release_id)}
                        </code>
                      </td>
                      <td>{r.agent_id}</td>
                      <td>{r.version}</td>
                      <td>{r.environment}</td>
                      <td>
                        <code className="fd-mono fd-mono--sm" title={r.checksum}>
                          {shortId(r.checksum, 8, 6)}
                        </code>
                      </td>
                      <td className="fd-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </TableShell>

          <TableShell title="Promoted" description="Current promoted release per agent and environment.">
            <table className="fd-table">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col">Environment</th>
                  <th scope="col">Active release</th>
                </tr>
              </thead>
              <tbody>
                {data.promoted.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="fd-empty-cell">
                      No promotion pointers yet.
                    </td>
                  </tr>
                ) : (
                  data.promoted.map((p: PromotedRow) => (
                    <tr key={`${p.agent_id}-${p.environment}`}>
                      <td>{p.agent_id}</td>
                      <td>{p.environment}</td>
                      <td>
                        <code className="fd-mono" title={p.release_id}>
                          {shortId(p.release_id)}
                        </code>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </TableShell>

          <TableShell title="Recent actions" description="Promotion and rollback attempts from the audit log.">
            <table className="fd-table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Action</th>
                  <th scope="col">Policy</th>
                  <th scope="col">Release</th>
                  <th scope="col">Environment</th>
                  <th scope="col">Reason</th>
                </tr>
              </thead>
              <tbody>
                {data.actions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="fd-empty-cell">
                      No actions yet.
                    </td>
                  </tr>
                ) : (
                  data.actions.map((a: ActionRow) => (
                    <tr key={a.action_id}>
                      <td className="fd-nowrap">{new Date(a.created_at).toLocaleString()}</td>
                      <td>{a.action}</td>
                      <td>
                        <Badge tone={a.policy_passed ? "pass" : "fail"}>
                          {a.policy_passed ? "PASS" : "FAIL"}
                        </Badge>
                      </td>
                      <td>
                        <code className="fd-mono" title={a.release_id}>
                          {shortId(a.release_id)}
                        </code>
                      </td>
                      <td>{a.environment}</td>
                      <td className="fd-reason">{a.reason}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </TableShell>

          <JsonPanel title="Raw timeline JSON" value={raw} defaultOpen={false} />
        </>
      ) : null}
    </>
  );
}
