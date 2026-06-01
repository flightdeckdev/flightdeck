import { useCallback, useEffect, useId, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ActionRow, MetricsPayload, PromotedRow, ReleaseRow, TimelinePayload } from "../api";
import { fetchMetrics, loadTimeline } from "../api";
import { useTimelineRefresh } from "../context/TimelineRefreshContext";
import { Badge } from "../components/Badge";
import { CopyTextButton } from "../components/CopyTextButton";
import { JsonPanel } from "../components/JsonPanel";
import { ReleaseLifecycleStrip } from "../components/ReleaseLifecycleStrip";
import { UI_READ_ONLY } from "../uiConfig";
import { searchParamsFromRecord } from "../urlSearch";
import { useDocumentTitle } from "../useDocumentTitle";

const OVERVIEW_POLL_MS = 30_000;

function shortId(id: string, keepStart = 10, keepEnd = 6) {
  if (id.length <= keepStart + keepEnd + 1) return id;
  return `${id.slice(0, keepStart)}…${id.slice(-keepEnd)}`;
}

function TableShell({
  title,
  description,
  toolbar,
  children,
}: {
  title: string;
  description?: string;
  toolbar?: ReactNode;
  children: ReactNode;
}) {
  const hid = useId();
  return (
    <section className="fd-card" aria-labelledby={hid}>
      <div className="fd-card__head">
        <h3 className="fd-card__title" id={hid}>
          {title}
        </h3>
        {description ? <p className="fd-card__desc">{description}</p> : null}
      </div>
      {toolbar ? <div className="fd-table-toolbar">{toolbar}</div> : null}
      <div className="fd-table-wrap fd-table-wrap--sticky">{children}</div>
    </section>
  );
}

export function OverviewPage() {
  useDocumentTitle("Overview");
  const [searchParams, setSearchParams] = useSearchParams();
  const focusReleaseId = (searchParams.get("release") ?? "").trim();

  const { generation } = useTimelineRefresh();
  const [data, setData] = useState<TimelinePayload | null>(null);
  const [metrics, setMetrics] = useState<MetricsPayload | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent === true;
    if (!silent) {
      setLoading(true);
    }
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
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void refresh({ silent: generation > 0 });
  }, [generation, refresh]);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void refresh({ silent: true });
    }, OVERVIEW_POLL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  const raw =
    data === null
      ? error ?? ""
      : JSON.stringify(
          { releases: data.releases, promoted: data.promoted, actions: data.actions },
          null,
          2,
        );

  const focusRelease = useMemo(() => {
    if (!data || !focusReleaseId) return null;
    return data.releases.find((r) => r.release_id === focusReleaseId) ?? null;
  }, [data, focusReleaseId]);

  const promotedBaselineForFocus = useMemo(() => {
    if (!data || !focusRelease) return null;
    return (
      data.promoted.find(
        (p) => p.agent_id === focusRelease.agent_id && p.environment === focusRelease.environment,
      ) ?? null
    );
  }, [data, focusRelease]);

  const clearReleaseFocus = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("release");
    setSearchParams(next);
  };

  const baselineReleaseForRow = (r: ReleaseRow) =>
    data?.promoted.find((p) => p.agent_id === r.agent_id && p.environment === r.environment)?.release_id ?? "";

  const releaseLookup = useMemo(() => {
    const m = new Map<string, ReleaseRow>();
    if (!data) return m;
    for (const r of data.releases) m.set(r.release_id, r);
    return m;
  }, [data]);

  const [filterAgent, setFilterAgent] = useState("");
  const [filterEnv, setFilterEnv] = useState("");
  const [filterPromoted, setFilterPromoted] = useState<"" | "live" | "not-live">("");

  const filteredReleases = useMemo(() => {
    if (!data) return [];
    const a = filterAgent.trim().toLowerCase();
    const e = filterEnv.trim().toLowerCase();
    return data.releases.filter((r) => {
      if (a && !r.agent_id.toLowerCase().includes(a)) return false;
      if (e && !r.environment.toLowerCase().includes(e)) return false;
      const baseline =
        data.promoted.find((p) => p.agent_id === r.agent_id && p.environment === r.environment)?.release_id ?? "";
      const isLive = baseline !== "" && baseline === r.release_id;
      if (filterPromoted === "live" && !isLive) return false;
      if (filterPromoted === "not-live" && isLive) return false;
      return true;
    });
  }, [data, filterAgent, filterEnv, filterPromoted]);

  const metricsPanelId = useId();
  const [metricsOpen, setMetricsOpen] = useState(false);

  return (
    <>
      <header className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Overview</h2>
          <p className="fd-page-sub fd-page-sub--tight">
            <strong>What changed?</strong> Scan releases and promotion pointers. <strong>Is it safe?</strong> Use{" "}
            <Link to="/diff">Diff</Link> for policy on baseline vs candidate. <strong>Can I ship?</strong> Promote from{" "}
            <Link to="/actions">Actions</Link> when policy passes.
          </p>
          <p className="fd-page-sub fd-page-sub--meta">
            Tables refresh every {OVERVIEW_POLL_MS / 1000}s while this tab is visible; mutations update after promote or
            rollback.
          </p>
        </div>
      </header>

      <ReleaseLifecycleStrip />

      {focusReleaseId && !loading && data ? (
        focusRelease ? (
          <section className="fd-release-hero" aria-labelledby="fd-release-hero-title">
            <h3 className="fd-release-hero__title" id="fd-release-hero-title">
              <span className="fd-release-hero__primary">
                {focusRelease.agent_id} v{focusRelease.version}
              </span>{" "}
              <span className="fd-release-hero__env">({focusRelease.environment})</span>
            </h3>
            <p className="fd-release-hero__meta">
              Release ID{" "}
              <code className="fd-mono fd-mono--sm" title={focusRelease.release_id}>
                {shortId(focusRelease.release_id, 14, 8)}
              </code>
              <CopyTextButton label="Release ID" value={focusRelease.release_id} buttonText="Copy ID" /> · checksum{" "}
              <code className="fd-mono fd-mono--sm" title={focusRelease.checksum}>
                {shortId(focusRelease.checksum, 8, 6)}
              </code>
              {promotedBaselineForFocus ? (
                <>
                  {" "}
                  · promoted baseline for this pair:{" "}
                  <code className="fd-mono fd-mono--sm" title={promotedBaselineForFocus.release_id}>
                    {shortId(promotedBaselineForFocus.release_id, 14, 8)}
                  </code>
                </>
              ) : (
                <> · no promoted pointer for this agent/environment yet</>
              )}
            </p>
            <div className="fd-release-hero__actions">
              <Link
                className="fd-btn fd-btn--primary"
                to={`/diff${searchParamsFromRecord({
                  baseline: promotedBaselineForFocus?.release_id ?? "",
                  candidate: focusRelease.release_id,
                  environment: focusRelease.environment,
                  window: "7d",
                })}`}
              >
                Open diff
              </Link>
              <Link
                className="fd-btn fd-btn--ghost"
                to={`/runs${searchParamsFromRecord({
                  release_id: focusRelease.release_id,
                  environment: focusRelease.environment,
                  window: "7d",
                })}`}
              >
                Open runs
              </Link>
              {UI_READ_ONLY ? null : (
                <Link
                  className="fd-btn fd-btn--ghost"
                  to={`/actions${searchParamsFromRecord({
                    release_id: focusRelease.release_id,
                    environment: focusRelease.environment,
                    window: "7d",
                  })}`}
                >
                  Promote
                </Link>
              )}
              <button type="button" className="fd-btn fd-btn--ghost" onClick={clearReleaseFocus}>
                Clear focus
              </button>
            </div>
          </section>
        ) : (
          <section className="fd-alert fd-alert--warn" role="status">
            <strong>Unknown release in URL.</strong> No registered release matches{" "}
            <code className="fd-mono fd-mono--sm">{shortId(focusReleaseId, 20, 10)}</code>.{" "}
            <button type="button" className="fd-btn fd-btn--ghost" onClick={clearReleaseFocus}>
              Clear <span className="fd-sr-only">release query</span>
            </button>
          </section>
        )
      ) : null}

      {error && !loading ? <p className="fd-alert fd-alert--error">{error}</p> : null}
      {loading ? (
        <div className="fd-loading-panel" aria-busy="true" aria-live="polite">
          <span className="fd-sr-only">Loading overview</span>
          <span className="fd-skeleton fd-skeleton--w60" />
          <span className="fd-skeleton fd-skeleton--w75 fd-skeleton--mt" />
          <span className="fd-skeleton fd-skeleton--w40 fd-skeleton--mt" />
        </div>
      ) : null}

      {data ? (
        <>
          {data.promoted.length === 0 && data.releases.length === 0 && data.actions.length === 0 ? (
            <section className="fd-card fd-card--hint" aria-label="Get started">
              <h3 className="fd-card__subtitle">No releases yet — register your first one</h3>
              <p className="fd-empty fd-m-0">
                Run <code className="fd-mono fd-mono--sm">flightdeck release register --agent my-agent --env local --version 0.1.0 --artifact ./build</code>
                {" "}then refresh. See <a className="fd-link" href="https://github.com/flightdeckdev/flightdeck#quickstart" target="_blank" rel="noreferrer">Quickstart docs</a>.
              </p>
            </section>
          ) : null}
          <TableShell
            title="Promoted releases"
            description="Current promoted release ID per agent and environment — compare with newer registrations below."
          >
            <table className="fd-table fd-table--hover fd-table--striped">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col">Environment</th>
                  <th scope="col">Promoted release</th>
                  <th scope="col">Version</th>
                  <th scope="col" className="fd-th-narrow">
                    Copy
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.promoted.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="fd-empty-cell">
                      No promotion pointers yet.
                    </td>
                  </tr>
                ) : (
                  data.promoted.map((p: PromotedRow) => {
                    const row = releaseLookup.get(p.release_id);
                    return (
                      <tr key={`${p.agent_id}-${p.environment}`}>
                        <td>{p.agent_id}</td>
                        <td>{p.environment}</td>
                        <td>
                          <Link
                            className="fd-link"
                            to={{ pathname: "/", search: searchParamsFromRecord({ release: p.release_id }) }}
                            title="Focus this release"
                          >
                            <code className="fd-mono" title={p.release_id}>
                              {shortId(p.release_id)}
                            </code>
                          </Link>
                        </td>
                        <td>{row?.version ?? "—"}</td>
                        <td>
                          <CopyTextButton label="Promoted release ID" value={p.release_id} buttonText="ID" />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </TableShell>

          <TableShell
            title="Registered releases"
            description="Artifacts in this workspace. “Live” means this row matches the promoted pointer for the same agent and environment."
            toolbar={
              <div className="fd-filter-row" role="group" aria-label="Filter releases">
                <label className="fd-field fd-field--compact">
                  <span className="fd-field__label">Agent contains</span>
                  <input
                    className="fd-input"
                    value={filterAgent}
                    onChange={(e) => setFilterAgent(e.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label className="fd-field fd-field--compact">
                  <span className="fd-field__label">Environment contains</span>
                  <input
                    className="fd-input"
                    value={filterEnv}
                    onChange={(e) => setFilterEnv(e.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label className="fd-field fd-field--compact">
                  <span className="fd-field__label">Promotion</span>
                  <select
                    className="fd-select"
                    value={filterPromoted}
                    onChange={(e) => setFilterPromoted(e.target.value as "" | "live" | "not-live")}
                  >
                    <option value="">All</option>
                    <option value="live">Live (promoted)</option>
                    <option value="not-live">Not promoted</option>
                  </select>
                </label>
                <div className="fd-inline fd-mt-md fd-grow-soft">
                  <span className="fd-muted fd-samples">
                    Showing {filteredReleases.length} of {data.releases.length}
                  </span>
                  {(filterAgent || filterEnv || filterPromoted) ? (
                    <button type="button" className="fd-btn fd-btn--ghost fd-btn--sm"
                      onClick={() => { setFilterAgent(""); setFilterEnv(""); setFilterPromoted(""); }}>
                      Clear filters
                    </button>
                  ) : null}
                </div>
              </div>
            }
          >
            <table className="fd-table fd-table--hover fd-table--striped">
              <thead>
                <tr>
                  <th scope="col">Primary</th>
                  <th scope="col">Release ID</th>
                  <th scope="col">Checksum</th>
                  <th scope="col">Created</th>
                  <th scope="col">Shortcuts</th>
                </tr>
              </thead>
              <tbody>
                {data.releases.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="fd-empty-cell">
                      No releases yet.
                    </td>
                  </tr>
                ) : filteredReleases.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="fd-empty-cell">
                      No releases match filters.
                    </td>
                  </tr>
                ) : (
                  filteredReleases.map((r: ReleaseRow) => {
                    const baseline = baselineReleaseForRow(r);
                    const isLive = baseline !== "" && baseline === r.release_id;
                    return (
                      <tr key={r.release_id}>
                        <td>
                          <div className="fd-cell-stack">
                            <span className="fd-cell-stack__main">
                              <strong>{r.agent_id}</strong> v{r.version}
                            </span>
                            <span className="fd-cell-stack__sub">{r.environment}</span>
                            {isLive ? (
                              <Badge tone="pass">Live</Badge>
                            ) : (
                              <Badge tone="neutral">Registered</Badge>
                            )}
                          </div>
                        </td>
                        <td>
                          <div className="fd-cell-inline">
                            <Link
                              to={{ pathname: "/", search: searchParamsFromRecord({ release: r.release_id }) }}
                              title="Focus this release in the overview hero"
                            >
                              <code className="fd-mono">{shortId(r.release_id)}</code>
                            </Link>
                            <CopyTextButton label="Release ID" value={r.release_id} buttonText="Copy" testId="overview-copy-release-row" />
                          </div>
                        </td>
                        <td>
                          <code className="fd-mono fd-mono--sm" title={r.checksum}>
                            {shortId(r.checksum, 8, 6)}
                          </code>
                        </td>
                        <td className="fd-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                        <td>
                          <div className="fd-table-actions">
                            <Link
                              to={{
                                pathname: "/diff",
                                search: searchParamsFromRecord({
                                  baseline,
                                  candidate: r.release_id,
                                  environment: r.environment,
                                  window: "7d",
                                }),
                              }}
                            >
                              Diff
                            </Link>
                            <Link
                              to={{
                                pathname: "/runs",
                                search: searchParamsFromRecord({
                                  release_id: r.release_id,
                                  environment: r.environment,
                                  window: "7d",
                                }),
                              }}
                            >
                              Runs
                            </Link>
                            {UI_READ_ONLY ? null : (
                              <Link
                                to={{
                                  pathname: "/actions",
                                  search: searchParamsFromRecord({
                                    release_id: r.release_id,
                                    environment: r.environment,
                                    window: "7d",
                                  }),
                                }}
                              >
                                Promote
                              </Link>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </TableShell>

          <TableShell title="Recent actions" description="Promotion and rollback attempts from the audit log.">
            <table className="fd-table fd-table--hover fd-table--striped">
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

          {metrics ? (
            <section className="fd-card fd-card--collapse" aria-label="Ledger metrics">
              <button
                type="button"
                className="fd-collapse-head"
                aria-expanded={metricsOpen}
                aria-controls={metricsPanelId}
                id={`${metricsPanelId}-btn`}
                data-testid="ledger-metrics-toggle"
                onClick={() => setMetricsOpen((o) => !o)}
              >
                <span className="fd-collapse-head__chevron" aria-hidden>
                  {metricsOpen ? "▾" : "▸"}
                </span>
                <span className="fd-collapse-head__title">Ledger metrics</span>
                <span className="fd-collapse-head__hint">
                  <code className="fd-mono fd-mono--sm">GET /v1/metrics</code> · schema v{metrics.schema_version}
                </span>
              </button>
              <div
                id={metricsPanelId}
                aria-labelledby={`${metricsPanelId}-btn`}
                hidden={!metricsOpen}
                className={metricsOpen ? "fd-collapse-body" : undefined}
              >
                {metricsOpen ? (
                  <>
                    <p className="fd-card__desc fd-metric-meta">
                      Generated {new Date(metrics.generated_at).toLocaleString()}.
                    </p>
                    <div className="fd-metric-grid">
                      <div className="fd-metric">
                        <div className="fd-metric__label">Releases</div>
                        <div className="fd-metric__row">
                          <span className="fd-metric__bc">{metrics.counters.releases_total}</span>
                        </div>
                        <p className="fd-metric__hint">
                          Registered <code className="fd-mono fd-mono--sm">release.yaml</code> bundles.
                        </p>
                      </div>
                      <div className="fd-metric">
                        <div className="fd-metric__label">Pricing tables</div>
                        <div className="fd-metric__row">
                          <span className="fd-metric__bc">{metrics.counters.pricing_tables_total}</span>
                        </div>
                        <p className="fd-metric__hint">Imported pricing snapshots for diff economics.</p>
                      </div>
                      <div className="fd-metric">
                        <div className="fd-metric__label">Run events</div>
                        <div className="fd-metric__row">
                          <span className="fd-metric__bc">{metrics.counters.run_events_total}</span>
                        </div>
                        <p className="fd-metric__hint">Ingested evidence (CLI or POST /v1/events).</p>
                      </div>
                      <div className="fd-metric">
                        <div className="fd-metric__label">Promoted pointers</div>
                        <div className="fd-metric__row">
                          <span className="fd-metric__bc">{metrics.counters.promoted_pointers_total}</span>
                        </div>
                        <p className="fd-metric__hint">Active pointers per agent/environment.</p>
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
                        <p className="fd-metric__hint">Ledger audit rows for promote/rollback.</p>
                      </div>
                    </div>
                  </>
                ) : null}
              </div>
            </section>
          ) : metricsError && !loading ? (
            <p className="fd-alert fd-alert--warn">Ledger metrics unavailable: {metricsError}</p>
          ) : null}

          <JsonPanel title="Raw timeline JSON" value={raw} defaultOpen={false} />
        </>
      ) : null}
    </>
  );
}
