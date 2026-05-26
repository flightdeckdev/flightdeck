import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ActionOutcomePayload, PromotionRequestListItem, WorkspacePublicPayload } from "../api";
import { fetchHealth, fetchJson, fetchPromotionRequests, fetchWorkspace } from "../api";
import { clientMutationTokenConfigured } from "../uiConfig";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
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

type Busy = null | "promote" | "rollback" | "request" | "confirm";

export function ActionsPage() {
  const [searchParams] = useSearchParams();
  const { notifyTimelineMutated } = useTimelineRefresh();
  const [workspace, setWorkspace] = useState<WorkspacePublicPayload | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [workspaceErr, setWorkspaceErr] = useState<string | null>(null);
  const [pendingList, setPendingList] = useState<PromotionRequestListItem[]>([]);
  const [pendingErr, setPendingErr] = useState<string | null>(null);
  const [pendingRefreshing, setPendingRefreshing] = useState(false);
  const [listNonce, setListNonce] = useState(0);

  const [actRelease, setActRelease] = useState("");
  const [actEnv, setActEnv] = useState("local");
  const [actWindow, setActWindow] = useState("7d");
  const [actReason, setActReason] = useState("");
  const [actOutcome, setActOutcome] = useState<ActionOutcomePayload | null>(null);
  const [actRaw, setActRaw] = useState<string | null>(null);
  const [actErr, setActErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy>(null);

  const [confirmRequestId, setConfirmRequestId] = useState("");
  const [confirmReason, setConfirmReason] = useState("");
  const [requestRaw, setRequestRaw] = useState<string | null>(null);

  const [mutationAuth, setMutationAuth] = useState<"bearer" | "loopback" | null>(null);
  const [healthChecked, setHealthChecked] = useState(false);

  const refreshPending = useCallback(async () => {
    if (!workspace?.promotion_requires_approval) return;
    setPendingErr(null);
    setPendingRefreshing(true);
    try {
      const r = await fetchPromotionRequests({ status: "pending", limit: 50 });
      setPendingList(r.requests);
    } catch (e) {
      setPendingErr(String(e));
    } finally {
      setPendingRefreshing(false);
    }
  }, [workspace?.promotion_requires_approval]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setWorkspaceLoading(true);
      setWorkspaceErr(null);
      try {
        const w = await fetchWorkspace();
        if (!cancelled) setWorkspace(w);
      } catch (e) {
        if (!cancelled) {
          setWorkspaceErr(String(e));
          setWorkspace(null);
        }
      } finally {
        if (!cancelled) setWorkspaceLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const h = await fetchHealth();
        if (!cancelled) {
          const m = h.mutation_auth;
          setMutationAuth(m === "bearer" || m === "loopback" ? m : null);
        }
      } catch {
        if (!cancelled) setMutationAuth(null);
      } finally {
        if (!cancelled) setHealthChecked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    void refreshPending();
  }, [refreshPending, listNonce]);

  useEffect(() => {
    const rid = searchParams.get("release_id");
    const env = searchParams.get("environment");
    const win = searchParams.get("window");
    if (rid !== null && rid.trim() !== "") setActRelease(rid.trim());
    if (env !== null && env.trim() !== "") setActEnv(env.trim());
    if (win !== null && win.trim() !== "") setActWindow(win.trim());
  }, [searchParams]);

  const runAction = async (path: "/v1/promote" | "/v1/rollback") => {
    setActErr(null);
    setActOutcome(null);
    setActRaw(null);
    setRequestRaw(null);
    const reason = actReason.trim();
    if (!reason) {
      setActErr("Reason is required.");
      return;
    }
    const label = path === "/v1/promote" ? "promotion" : "rollback";
    const rid = actRelease.trim();
    const env = actEnv.trim();
    if (
      !window.confirm(
        `Run ${label} for release ${rid} in ${env}? The server evaluates policy on this window before changing the ledger.`,
      )
    ) {
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

  const runRequestPromotion = async () => {
    setActErr(null);
    setActOutcome(null);
    setActRaw(null);
    setRequestRaw(null);
    const reason = actReason.trim();
    if (!reason) {
      setActErr("Reason is required for the promotion request.");
      return;
    }
    if (!window.confirm("Create a pending promotion request for this release?")) {
      return;
    }
    setBusy("request");
    try {
      const data = await fetchJson<unknown>("/v1/promote/request", {
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
      setRequestRaw(JSON.stringify(data, null, 2));
      if (isRecord(data) && typeof data.request_id === "string") {
        setConfirmRequestId(data.request_id);
      }
      setListNonce((n) => n + 1);
      notifyTimelineMutated();
    } catch (e) {
      setActErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  const runConfirmPromotion = async () => {
    setActErr(null);
    setActOutcome(null);
    setActRaw(null);
    const rid = confirmRequestId.trim();
    const ar = confirmReason.trim();
    if (!rid) {
      setActErr("Request ID is required to confirm.");
      return;
    }
    if (!ar) {
      setActErr("Approval reason is required.");
      return;
    }
    if (
      !window.confirm(
        `Approve request ${shortId(rid, 12, 6)} and run promote if policy passes? The promoted pointer updates only when the server reports policy PASS.`,
      )
    ) {
      return;
    }
    setBusy("confirm");
    try {
      const data = await fetchJson<unknown>("/v1/promote/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: rid,
          approval_reason: ar,
          actor: "react-ui",
        }),
      });
      setActOutcome(pickOutcome(data));
      setActRaw(JSON.stringify(data, null, 2));
      setListNonce((n) => n + 1);
      notifyTimelineMutated();
    } catch (e) {
      setActErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  const approvalOn = workspace?.promotion_requires_approval === true;
  const canMutate = !workspaceLoading && workspace !== null;
  const clientTokenOn = clientMutationTokenConfigured();
  const showBearerTokenHint =
    canMutate && healthChecked && mutationAuth === "bearer" && !clientTokenOn;

  return (
    <>
      <header className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Promote & rollback</h2>
          <p className="fd-page-sub fd-page-sub--tight">
            <strong>What changed?</strong> You choose the candidate release and window. <strong>Is it safe?</strong> The
            server evaluates policy before mutating the ledger. <strong>Can I ship?</strong> Promotion succeeds only when
            policy passes (or follow request/confirm when approval is required).
          </p>
          <p className="fd-page-sub fd-page-sub--meta">
            Same HTTP contract as the CLI. When{" "}
            <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code> is set, include it via{" "}
            <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code> so reads and mutations send{" "}
            <code className="fd-mono fd-mono--sm">Authorization: Bearer</code>.
          </p>
        </div>
      </header>

      {workspaceErr ? <p className="fd-alert fd-alert--error">{workspaceErr}</p> : null}

      {workspaceLoading && !workspaceErr ? (
        <section className="fd-card" aria-busy="true" aria-label="Workspace status">
          <div className="fd-loading-panel">
            <span className="fd-sr-only">Loading workspace</span>
            <span className="fd-skeleton fd-skeleton--w60" />
            <span className="fd-skeleton fd-skeleton--w75 fd-skeleton--mt" />
            <span className="fd-skeleton fd-skeleton--w40 fd-skeleton--mt" />
          </div>
        </section>
      ) : null}

      {workspace ? (
        <section className="fd-card">
          <p className="fd-muted fd-samples">
            Server <span className="fd-mono fd-mono--sm">{workspace.server_version}</span>
            {" · "}
            Catalog{" "}
            <Badge tone={workspace.pricing_catalog_configured ? "pass" : "neutral"}>
              {workspace.pricing_catalog_configured ? "configured" : "not configured"}
            </Badge>
            {" · "}
            Promote{" "}
            <Badge tone={approvalOn ? "neutral" : "pass"}>
              {approvalOn ? "human approval required" : "direct promotion"}
            </Badge>
          </p>
          {approvalOn ? (
            <p className="fd-muted fd-samples">
              This workspace uses <code className="fd-mono fd-mono--sm">promotion_requires_approval</code>. Use{" "}
              <strong>Request promotion</strong> then <strong>Confirm promotion</strong> (or CLI{" "}
              <code className="fd-mono fd-mono--sm">release promote-request</code> /{" "}
              <code className="fd-mono fd-mono--sm">promote-confirm</code>).{" "}
              <code className="fd-mono fd-mono--sm">POST /v1/promote</code> alone will be rejected.
            </p>
          ) : (
            <p className="fd-muted fd-samples">
              <code className="fd-mono fd-mono--sm">POST /v1/promote</code> is allowed when policy passes. Turn on{" "}
              <code className="fd-mono fd-mono--sm">promotion_requires_approval</code> in{" "}
              <code className="fd-mono fd-mono--sm">flightdeck.yaml</code> for a two-step gate.
            </p>
          )}
        </section>
      ) : null}

      <section className="fd-card" aria-busy={!canMutate}>
        {approvalOn ? (
          <div className="fd-card__head">
            <h3 className="fd-card__subtitle">1. Request a promotion</h3>
            <p className="fd-card__desc">
              Submit a reason and request; promotion stays pending until step 3. Rollback below still runs immediately when
              policy allows.
            </p>
          </div>
        ) : (
          <div className="fd-card__head">
            <h3 className="fd-card__subtitle">Promote or rollback</h3>
            <p className="fd-card__desc">Policy is evaluated on the server for the window you set.</p>
          </div>
        )}
        <div className="fd-form-grid">
          <label className="fd-field">
            <span className="fd-field__label">Release ID</span>
            <input
              className="fd-input"
              value={actRelease}
              onChange={(e) => setActRelease(e.target.value)}
              disabled={!canMutate}
            />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Environment</span>
            <input
              className="fd-input"
              value={actEnv}
              onChange={(e) => setActEnv(e.target.value)}
              disabled={!canMutate}
            />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Window</span>
            <input
              className="fd-input"
              value={actWindow}
              onChange={(e) => setActWindow(e.target.value)}
              disabled={!canMutate}
            />
          </label>
          <label className="fd-field fd-field--full">
            <span className="fd-field__label">
              Reason
              <span className="fd-field__required" aria-hidden="true">
                *
              </span>
            </span>
            <input
              className={`fd-input${actErr?.includes("Reason is required") ? " fd-input--invalid" : ""}`}
              value={actReason}
              onChange={(e) => setActReason(e.target.value)}
              disabled={!canMutate}
              required
              aria-required="true"
            />
          </label>
        </div>
        {!canMutate ? (
          <p className="fd-muted fd-samples" aria-live="polite">
            Loading workspace mode…
          </p>
        ) : (
          <p className="fd-muted fd-samples" aria-live="polite">
            <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code>{" "}
            {clientTokenOn ? "is configured for this UI build." : "is not set in this UI build."}
          </p>
        )}
        <div className="fd-actions fd-actions--align-center">
          {approvalOn ? (
            <Button
              variant="primary"
              disabled={!canMutate || busy !== null}
              loading={busy === "request"}
              loadingLabel="Requesting…"
              onClick={() => void runRequestPromotion()}
            >
              Request promotion
            </Button>
          ) : (
            <Button
              variant="primary"
              disabled={!canMutate || busy !== null}
              loading={busy === "promote"}
              loadingLabel="Promoting…"
              onClick={() => void runAction("/v1/promote")}
            >
              Promote
            </Button>
          )}
          <Button
            variant="danger"
            disabled={!canMutate || busy !== null}
            loading={busy === "rollback"}
            loadingLabel="Rolling back…"
            onClick={() => void runAction("/v1/rollback")}
          >
            Rollback
          </Button>
          {showBearerTokenHint ? (
            <span className="fd-muted fd-samples fd-grow-soft">
              Server uses Bearer for mutations — set{" "}
              <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code> to match the server.
            </span>
          ) : null}
        </div>
      </section>

      {approvalOn ? (
        <>
          <section className="fd-card" aria-busy={pendingRefreshing}>
            <div className="fd-card__head fd-card__head--row">
              <div>
                <h3 className="fd-card__subtitle">2. Pending promotion requests</h3>
                <p className="fd-card__desc">
                  Open requests waiting for an approver. Use <strong>Use for confirm</strong> to copy an ID into step 3.
                </p>
              </div>
              <Button
                variant="ghost"
                disabled={pendingRefreshing || busy !== null}
                loading={pendingRefreshing}
                loadingLabel="Refreshing…"
                onClick={() => void refreshPending()}
              >
                Refresh list
              </Button>
            </div>
            {pendingErr ? <p className="fd-alert fd-alert--error">{pendingErr}</p> : null}
            {pendingList.length === 0 ? (
              <p className="fd-muted">No pending requests. After you request a promotion, it appears here.</p>
            ) : (
              <div className="fd-table-wrap fd-table-wrap--sticky">
                <table className="fd-table fd-table--hover">
                  <thead>
                    <tr>
                      <th scope="col">Request ID</th>
                      <th scope="col">Release</th>
                      <th scope="col">Env</th>
                      <th scope="col">Created</th>
                      <th scope="col">Confirm</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingList.map((row) => (
                      <tr key={row.request_id}>
                        <td>
                          <code className="fd-mono fd-mono--sm" title={row.request_id}>
                            {shortId(row.request_id, 14, 8)}
                          </code>
                        </td>
                        <td>
                          <code className="fd-mono fd-mono--sm">{shortId(row.release_id)}</code>
                        </td>
                        <td>{row.environment}</td>
                        <td className="fd-muted">{row.created_at}</td>
                        <td>
                          <button
                            type="button"
                            className="fd-btn fd-btn--ghost fd-btn--sm"
                            disabled={busy !== null}
                            aria-label={`Use request ${shortId(row.request_id, 14, 8)} for confirm step`}
                            onClick={() => setConfirmRequestId(row.request_id)}
                          >
                            Use for confirm
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="fd-card">
            <div className="fd-card__head">
              <h3 className="fd-card__subtitle">3. Confirm a request</h3>
              <p className="fd-card__desc">
                Paste the full request ID (or pick from the table), add an approval reason, then confirm. This runs the same
                policy gate as direct promote.
              </p>
            </div>
            <div className="fd-form-grid">
              <label className="fd-field fd-field--full">
                <span className="fd-field__label">Request ID</span>
                <input
                  className="fd-input"
                  value={confirmRequestId}
                  onChange={(e) => setConfirmRequestId(e.target.value)}
                  placeholder="From the table above or promote-request output"
                />
              </label>
              <label className="fd-field fd-field--full">
                <span className="fd-field__label">Approval reason</span>
                <input
                  className="fd-input"
                  value={confirmReason}
                  onChange={(e) => setConfirmReason(e.target.value)}
                  placeholder="Why you are approving this promotion"
                />
              </label>
            </div>
            <div className="fd-actions">
              <Button
                variant="primary"
                disabled={busy !== null}
                loading={busy === "confirm"}
                loadingLabel="Confirming…"
                onClick={() => void runConfirmPromotion()}
              >
                Confirm promotion
              </Button>
            </div>
          </section>
        </>
      ) : null}

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
                  <code className="fd-mono fd-mono--sm" title={actOutcome.baseline_release_id}>
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

      {requestRaw ? <JsonPanel title="Promotion request (raw JSON)" value={requestRaw} defaultOpen /> : null}

      {actRaw ? (
        <JsonPanel title="Raw response JSON" value={actRaw} defaultOpen={actOutcome === null} />
      ) : null}
    </>
  );
}
