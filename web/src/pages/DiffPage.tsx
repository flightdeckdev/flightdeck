import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchJson } from "../api";
import { JsonPanel } from "../components/JsonPanel";
import { DiffChangeImpact } from "../components/diff/DiffChangeImpact";
import { DiffDecisionCard } from "../components/diff/DiffDecisionCard";
import { DiffPolicyPanel } from "../components/diff/DiffPolicyPanel";
import { DiffReleaseTwin } from "../components/diff/DiffReleaseTwin";
import { DiffVerdictStack } from "../components/diff/DiffVerdictStack";
import { Button } from "../components/Button";
import {
  type DiffJson,
  isRecord,
  pickPolicy,
  pickPricing,
} from "../components/diff/diffPayload";
import { UI_READ_ONLY } from "../uiConfig";
import { pickTrimmedSearch, searchParamsFromRecord } from "../urlSearch";
import { useDocumentTitle } from "../useDocumentTitle";

export function DiffPage() {
  useDocumentTitle("Run diff");
  const [searchParams, setSearchParams] = useSearchParams();
  const [diffResultSeq, setDiffResultSeq] = useState(0);
  const [diffBaseline, setDiffBaseline] = useState("");
  const [diffCandidate, setDiffCandidate] = useState("");
  const [diffWindow, setDiffWindow] = useState("7d");
  const [diffEnv, setDiffEnv] = useState("local");
  const [diffOut, setDiffOut] = useState<DiffJson | null>(null);
  const [diffErr, setDiffErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDiffBaseline(pickTrimmedSearch(searchParams, "baseline"));
    setDiffCandidate(pickTrimmedSearch(searchParams, "candidate"));
    const w = pickTrimmedSearch(searchParams, "window");
    setDiffWindow(w !== "" ? w : "7d");
    const e = pickTrimmedSearch(searchParams, "environment");
    setDiffEnv(e !== "" ? e : "local");
  }, [searchParams]);

  const runDiff = async () => {
    setDiffErr(null);
    setDiffOut(null);
    setBusy(true);
    const baseline = diffBaseline.trim();
    const candidate = diffCandidate.trim();
    const windowVal = diffWindow.trim();
    const envVal = diffEnv.trim();
    const nextParams = new URLSearchParams();
    if (baseline) nextParams.set("baseline", baseline);
    if (candidate) nextParams.set("candidate", candidate);
    nextParams.set("window", windowVal || "7d");
    if (envVal) nextParams.set("environment", envVal);
    setSearchParams(nextParams);
    try {
      const body = {
        baseline_release_id: baseline,
        candidate_release_id: candidate,
        window: windowVal,
        environment: envVal || null,
      };
      const data = await fetchJson<DiffJson>("/v1/diff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setDiffOut(data);
      setDiffResultSeq((n) => n + 1);
    } catch (e) {
      setDiffErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const m = diffOut?.metrics;
  const s = diffOut?.samples;
  const metrics = isRecord(m) ? m : null;
  const samples = isRecord(s) ? s : null;
  const policy = diffOut ? pickPolicy(diffOut) : null;
  const pricing = diffOut ? pickPricing(diffOut) : null;

  const promoteSearch =
    !UI_READ_ONLY && diffCandidate.trim() !== ""
      ? searchParamsFromRecord({
          release_id: diffCandidate.trim(),
          environment: diffEnv.trim(),
          window: diffWindow.trim(),
        })
      : "";

  return (
    <>
      <header className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Run diff</h2>
          <p className="fd-page-sub fd-page-sub--tight">
            <strong>What changed?</strong> Baseline vs candidate releases over a window. <strong>Is it safe?</strong> Policy
            verdict below. <strong>Can I ship?</strong> Use promote when policy passes —{" "}
            <Link to="/actions">Actions</Link>.
          </p>
          <p className="fd-page-sub fd-page-sub--meta">
            <Link to="/">Overview</Link> shortcuts and URLs can prefill{" "}
            <code className="fd-mono fd-mono--sm">baseline</code>,{" "}
            <code className="fd-mono fd-mono--sm">candidate</code>,{" "}
            <code className="fd-mono fd-mono--sm">window</code>,{" "}
            <code className="fd-mono fd-mono--sm">environment</code>; click <strong>Compute diff</strong> to run (same
            contract as <code className="fd-mono fd-mono--sm">flightdeck release diff</code>).
          </p>
        </div>
      </header>

      <section className="fd-card" aria-busy={busy} aria-label="Diff query">
        <div className="fd-form-grid">
          <label className="fd-field">
            <span className="fd-field__label">Baseline release ID</span>
            <input
              className="fd-input"
              value={diffBaseline}
              onChange={(e) => setDiffBaseline(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Candidate release ID</span>
            <input
              className="fd-input"
              value={diffCandidate}
              onChange={(e) => setDiffCandidate(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Window</span>
            <input className="fd-input" value={diffWindow} onChange={(e) => setDiffWindow(e.target.value)} />
          </label>
          <label className="fd-field">
            <span className="fd-field__label">Environment</span>
            <input className="fd-input" value={diffEnv} onChange={(e) => setDiffEnv(e.target.value)} />
          </label>
        </div>
        <div className="fd-actions">
          <Button variant="primary" loading={busy} loadingLabel="Computing…" onClick={() => void runDiff()}>
            Compute diff
          </Button>
        </div>
      </section>

      {diffErr ? <p className="fd-alert fd-alert--error">{diffErr}</p> : null}

      {!diffOut && !diffErr ? (
        <section className="fd-card fd-card--hint" aria-label="Diff help">
          <p className="fd-empty fd-m-0">
            Enter <strong>baseline</strong> and <strong>candidate</strong> release IDs, then <strong>Compute diff</strong>.
            Same contract as <code className="fd-mono fd-mono--sm">POST /v1/diff</code> and{" "}
            <code className="fd-mono fd-mono--sm">flightdeck release diff</code> — structured sections below summarize policy,
            samples, pricing/catalog hints, and rollups; open <strong>Raw diff JSON</strong> for the full payload.
          </p>
        </section>
      ) : null}

      {diffOut ? (
        <>
          <DiffReleaseTwin
            diffBaseline={diffBaseline}
            diffCandidate={diffCandidate}
            diffEnv={diffEnv}
            diffWindow={diffWindow}
            pricing={pricing}
          />

          <DiffVerdictStack policy={policy} />

          {policy ? <DiffPolicyPanel policy={policy} /> : null}

          <DiffDecisionCard policy={policy} promoteSearch={promoteSearch} />

          <DiffChangeImpact samples={samples} metrics={metrics} pricing={pricing} pricingResetKey={diffResultSeq} />

          <JsonPanel title="Raw diff JSON" value={JSON.stringify(diffOut, null, 2)} defaultOpen={false} />
        </>
      ) : null}
    </>
  );
}
