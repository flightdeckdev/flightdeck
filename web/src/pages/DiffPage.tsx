import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchJson } from "../api";
import { Badge } from "../components/Badge";
import { JsonPanel } from "../components/JsonPanel";
import { UI_READ_ONLY } from "../uiConfig";
import { pickTrimmedSearch, searchParamsFromRecord } from "../urlSearch";

type DiffJson = Record<string, unknown>;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function pickPolicy(data: DiffJson): {
  passed: boolean;
  reasons: string[];
  evaluatedAt: string | null;
} | null {
  const p = data.policy;
  if (!isRecord(p)) return null;
  const passed = p.passed;
  const reasons = p.reasons;
  const ev = p.evaluated_at;
  return {
    passed: passed === true,
    reasons: Array.isArray(reasons) ? reasons.filter((x): x is string => typeof x === "string") : [],
    evaluatedAt: typeof ev === "string" ? ev : null,
  };
}

type CatalogInfo = {
  enabled: boolean;
  version: string | null;
  baselineSlot: string | null;
  candidateSlot: string | null;
  baselineCost: number | null;
  candidateCost: number | null;
  deltaCost: number | null;
  warnings: string[];
};

type PricingInfo = {
  baselineProvider: string;
  baselineVersion: string;
  baselineModel: string;
  candidateProvider: string;
  candidateVersion: string;
  candidateModel: string;
  changed: boolean;
  prices: PricingPrices | null;
  warnings: string[];
  hints: string[];
  catalog: CatalogInfo | null;
};

type PricingPrices = {
  baselineInput: number | null;
  baselineOutput: number | null;
  candidateInput: number | null;
  candidateOutput: number | null;
};

function pickPrices(p: Record<string, unknown>): PricingPrices | null {
  const block = p.prices;
  if (!isRecord(block)) return null;
  const numOrNull = (k: string): number | null =>
    typeof block[k] === "number" && Number.isFinite(block[k]) ? (block[k] as number) : null;
  return {
    baselineInput: numOrNull("baseline_input_usd_per_1k_tokens"),
    baselineOutput: numOrNull("baseline_output_usd_per_1k_tokens"),
    candidateInput: numOrNull("candidate_input_usd_per_1k_tokens"),
    candidateOutput: numOrNull("candidate_output_usd_per_1k_tokens"),
  };
}

/**
 * Coerces the `pricing` block from `/v1/diff` into a typed view.  The contract
 * is set by the route in `src/flightdeck/server/routes/actions.py`.
 */
function pickCatalog(block: Record<string, unknown>): CatalogInfo {
  const rawW = block.warnings;
  const warnings = Array.isArray(rawW) ? rawW.filter((x): x is string => typeof x === "string") : [];
  const numOrNull = (k: string): number | null =>
    typeof block[k] === "number" && Number.isFinite(block[k]) ? (block[k] as number) : null;
  const strOrNull = (k: string): string | null =>
    typeof block[k] === "string" ? (block[k] as string) : null;
  return {
    enabled: block.enabled === true,
    version: strOrNull("catalog_version"),
    baselineSlot: strOrNull("baseline_slot_id"),
    candidateSlot: strOrNull("candidate_slot_id"),
    baselineCost: numOrNull("baseline_cost_per_run_usd"),
    candidateCost: numOrNull("candidate_cost_per_run_usd"),
    deltaCost: numOrNull("delta_cost_per_run_usd"),
    warnings,
  };
}

function pickPricing(data: DiffJson): PricingInfo | null {
  const p = data.pricing;
  if (!isRecord(p)) return null;
  const get = (k: string): string => (typeof p[k] === "string" ? (p[k] as string) : "");
  const rawWarnings = p.warnings;
  const warnings = Array.isArray(rawWarnings)
    ? rawWarnings.filter((x): x is string => typeof x === "string")
    : [];
  const rawHints = p.hints;
  const hints = Array.isArray(rawHints) ? rawHints.filter((x): x is string => typeof x === "string") : [];
  const catRaw = p.catalog;
  const catalog = isRecord(catRaw) ? pickCatalog(catRaw) : null;
  return {
    baselineProvider: get("baseline_provider"),
    baselineVersion: get("baseline_version"),
    baselineModel: get("baseline_model"),
    candidateProvider: get("candidate_provider"),
    candidateVersion: get("candidate_version"),
    candidateModel: get("candidate_model"),
    changed: p.pricing_or_model_changed === true,
    prices: pickPrices(p),
    warnings,
    hints,
    catalog,
  };
}

function Metric({
  label,
  baseline,
  candidate,
  delta,
  suffix = "",
}: {
  label: string;
  baseline: string;
  candidate: string;
  delta?: string;
  suffix?: string;
}) {
  return (
    <div className="fd-metric">
      <div className="fd-metric__label">{label}</div>
      <div className="fd-metric__row">
        <span className="fd-metric__bc">
          <span className="fd-metric__tag">B</span> {baseline}
          {suffix}
        </span>
        <span className="fd-metric__arrow" aria-hidden>
          →
        </span>
        <span className="fd-metric__bc">
          <span className="fd-metric__tag">C</span> {candidate}
          {suffix}
        </span>
      </div>
      {delta ? <div className="fd-metric__delta">{delta}</div> : null}
    </div>
  );
}

export function DiffPage() {
  const [searchParams, setSearchParams] = useSearchParams();
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

  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? String(v) : "—");
  const pct = (v: unknown) =>
    typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(2)}%` : "—";

  return (
    <>
      <header className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Run diff</h2>
          <p className="fd-page-sub">
            Compare baseline vs candidate over a window. Same contract as{" "}
            <code className="fd-mono fd-mono--sm">flightdeck release diff</code>.{" "}
            <Link to="/">Overview</Link> shortcuts and shared URLs can prefill{" "}
            <code className="fd-mono fd-mono--sm">baseline</code>,{" "}
            <code className="fd-mono fd-mono--sm">candidate</code>,{" "}
            <code className="fd-mono fd-mono--sm">window</code>, and{" "}
            <code className="fd-mono fd-mono--sm">environment</code> query params; click{" "}
            <strong>Compute diff</strong> to run.
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
          <button type="button" className="fd-btn fd-btn--primary" disabled={busy} onClick={() => void runDiff()}>
            {busy ? "Computing…" : "Compute diff"}
          </button>
          {busy ? (
            <span className="fd-sr-only" aria-live="polite">
              Computing diff
            </span>
          ) : null}
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
          {policy ? (
            <div
              className={`fd-verdict-banner ${policy.passed ? "fd-verdict-banner--pass" : "fd-verdict-banner--fail"}`}
              role="status"
              aria-live="polite"
            >
              <strong className="fd-verdict-banner__title">
                {policy.passed ? "Policy PASS — safe to consider promotion" : "Policy FAIL — do not ship this candidate"}
              </strong>
              {policy.evaluatedAt ? (
                <p className="fd-muted fd-m-0 fd-mt-md">
                  evaluated_at <span className="fd-mono fd-mono--sm">{policy.evaluatedAt}</span>
                </p>
              ) : null}
              {policy.reasons.length > 0 ? (
                <ul className="fd-verdict-banner__reasons">
                  {policy.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : policy.passed ? (
                <p className="fd-muted fd-m-0 fd-mt-md">No detailed constraint messages returned.</p>
              ) : (
                <p className="fd-muted fd-m-0 fd-mt-md">No reasons listed — inspect raw JSON and server policy.</p>
              )}
              {!UI_READ_ONLY && diffCandidate.trim() !== "" ? (
                <p className="fd-inline-nav fd-mb-0 fd-mt-md">
                  <Link
                    className="fd-btn fd-btn--primary"
                    to={{
                      pathname: "/actions",
                      search: searchParamsFromRecord({
                        release_id: diffCandidate.trim(),
                        environment: diffEnv.trim(),
                        window: diffWindow.trim(),
                      }),
                    }}
                  >
                    Continue to promote
                  </Link>
                  <span className="fd-muted-inline fd-ml-sm">
                    Uses candidate release ID and this page&apos;s window/environment (reason still required).
                  </span>
                </p>
              ) : null}
            </div>
          ) : (
            <div className="fd-alert fd-alert--warn" role="status">
              <strong>No policy block</strong> in this diff response — confirm server version and request payload before
              treating the outcome as gated.
            </div>
          )}

          <section className="fd-card" aria-label="Diff result summary">
            <div className="fd-card__head">
              <h3 className="fd-card__subtitle">Diff result</h3>
            </div>
            <div className="fd-diff-stack">
              <div className="fd-diff-section" role="region" aria-labelledby="diff-sec-policy">
                <h4 className="fd-diff-section__title" id="diff-sec-policy">
                  Policy gate
                </h4>
                {policy ? (
                  <div className="fd-diff-section__body">
                    <Badge tone={policy.passed ? "pass" : "fail"}>{policy.passed ? "PASS" : "FAIL"}</Badge>
                    {policy.evaluatedAt ? (
                      <span className="fd-muted-inline fd-ml-md">evaluated_at {policy.evaluatedAt}</span>
                    ) : null}
                    {policy.reasons.length > 0 ? (
                      <ul className="fd-reasons fd-mt-md">
                        {policy.reasons.map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="fd-muted-p">
                        No policy constraint messages (pass with empty reasons, or policy omitted).
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="fd-muted fd-diff-section__body">No policy block in this response.</p>
                )}
              </div>

              <div className="fd-diff-section" role="region" aria-labelledby="diff-sec-samples">
                <h4 className="fd-diff-section__title" id="diff-sec-samples">
                  Evidence window
                </h4>
                {samples ? (
                  <p className="fd-diff-section__body fd-muted fd-m-0">
                    Baseline runs: <strong>{num(samples.baseline_runs)}</strong> · Candidate runs:{" "}
                    <strong>{num(samples.candidate_runs)}</strong> · Confidence:{" "}
                    <strong>{String(samples.confidence ?? "—")}</strong>
                    {typeof samples.confidence_reason === "string" ? ` — ${samples.confidence_reason}` : null}
                  </p>
                ) : (
                  <p className="fd-muted fd-diff-section__body">No sample counts in this response.</p>
                )}
              </div>

              <div className="fd-diff-section" role="region" aria-labelledby="diff-sec-pricing">
                <h4 className="fd-diff-section__title" id="diff-sec-pricing">
                  Pricing, model, and catalog
                </h4>
                {pricing ? (
                  <div className="fd-diff-section__body">
                    <p className="fd-muted fd-block-mb-065 fd-type-desc">
                      Resolved models:{" "}
                      <code className="fd-mono fd-mono--sm">
                        {pricing.baselineProvider}/{pricing.baselineVersion} {pricing.baselineModel}
                      </code>{" "}
                      →{" "}
                      <code className="fd-mono fd-mono--sm">
                        {pricing.candidateProvider}/{pricing.candidateVersion} {pricing.candidateModel}
                      </code>
                      {pricing.changed ? (
                        <span className="fd-badge fd-badge--warn fd-ml-sm">pricing/model changed</span>
                      ) : (
                        <span className="fd-badge fd-badge--neutral fd-ml-sm">unchanged</span>
                      )}
                    </p>
                    {(() => {
                      const bp = pricing.baselineProvider.trim();
                      const cp = pricing.candidateProvider.trim();
                      const bv = pricing.baselineVersion.trim();
                      const cv = pricing.candidateVersion.trim();
                      const providerSkew = bp.length > 0 && cp.length > 0 && bp !== cp;
                      const versionSkew = bv.length > 0 && cv.length > 0 && bv !== cv;
                      if (!providerSkew && !versionSkew) return null;
                      return (
                        <p className="fd-alert fd-alert--warn fd-block-mb-065" role="status">
                          {versionSkew ? (
                            <>
                              Imported <strong>pricing table versions</strong> differ (
                              <code className="fd-mono fd-mono--sm">{bv}</code> vs{" "}
                              <code className="fd-mono fd-mono--sm">{cv}</code>).{" "}
                            </>
                          ) : null}
                          {providerSkew ? (
                            <>
                              <strong>Providers</strong> differ (
                              <code className="fd-mono fd-mono--sm">{bp}</code> vs{" "}
                              <code className="fd-mono fd-mono--sm">{cp}</code>).{" "}
                            </>
                          ) : null}
                          Treat per-1k and catalog lines below as resolved per release; skew can change comparability.
                        </p>
                      );
                    })()}
                    {pricing.warnings.length > 0 ? (
                      <>
                        <p className="fd-diff-section__title fd-mb-035">Pricing warnings</p>
                        <ul className="fd-alert fd-alert--warn fd-reasons fd-mt-0">
                          {pricing.warnings.map((w) => (
                            <li key={w}>{w}</li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                    {pricing.hints.length > 0 ? (
                      <>
                        <p className="fd-diff-section__title fd-block-mt-065-mb-035">Hints</p>
                        <ul className="fd-alert fd-alert--info fd-reasons fd-mt-0">
                          {pricing.hints.map((h) => (
                            <li key={h}>{h}</li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                    {pricing.catalog && (pricing.catalog.enabled || pricing.catalog.warnings.length > 0) ? (
                      <>
                        <p className="fd-diff-section__title fd-block-mt-065-mb-035">Pricing catalog</p>
                        <div className="fd-alert fd-alert--info fd-mt-0">
                          {pricing.catalog.enabled ? (
                            <p className="fd-m-0 fd-mb-035">
                              Catalog v{pricing.catalog.version ?? "—"} · slots{" "}
                              <code className="fd-mono fd-mono--sm">{pricing.catalog.baselineSlot ?? "—"}</code> →{" "}
                              <code className="fd-mono fd-mono--sm">{pricing.catalog.candidateSlot ?? "—"}</code>
                              {pricing.catalog.baselineCost !== null &&
                              pricing.catalog.candidateCost !== null &&
                              pricing.catalog.deltaCost !== null ? (
                                <>
                                  <br />
                                  Comparable cost/run: {pricing.catalog.baselineCost.toFixed(6)} →{" "}
                                  {pricing.catalog.candidateCost.toFixed(6)} (Δ{" "}
                                  {pricing.catalog.deltaCost >= 0 ? "+" : ""}
                                  {pricing.catalog.deltaCost.toFixed(6)})
                                </>
                              ) : null}
                            </p>
                          ) : (
                            <p className="fd-muted fd-m-0">
                              Catalog disabled or incomplete for this diff.
                            </p>
                          )}
                          {pricing.catalog.warnings.length > 0 ? (
                            <ul className="fd-reasons fd-mb-0">
                              {pricing.catalog.warnings.map((w) => (
                                <li key={w}>{w}</li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      </>
                    ) : null}
                    {pricing.changed &&
                    pricing.prices &&
                    pricing.prices.baselineInput !== null &&
                    pricing.prices.candidateInput !== null &&
                    pricing.prices.baselineOutput !== null &&
                    pricing.prices.candidateOutput !== null ? (
                      <>
                        <p className="fd-diff-section__title fd-block-mt-065-mb-035">Per-1k token prices (USD)</p>
                        <dl className="fd-dl fd-dl--inline fd-m-0">
                          <div>
                            <dt>Input / 1k</dt>
                            <dd className="fd-mono fd-mono--sm">
                              {pricing.prices.baselineInput.toFixed(6)} → {pricing.prices.candidateInput.toFixed(6)}
                            </dd>
                          </div>
                          <div>
                            <dt>Output / 1k</dt>
                            <dd className="fd-mono fd-mono--sm">
                              {pricing.prices.baselineOutput.toFixed(6)} → {pricing.prices.candidateOutput.toFixed(6)}
                            </dd>
                          </div>
                        </dl>
                        <p className="fd-muted-xs fd-mt-md">
                          Cost rollups reflect pricing table and model identity; compare with catalog lines above when
                          configured.
                        </p>
                      </>
                    ) : null}
                  </div>
                ) : (
                  <p className="fd-muted fd-diff-section__body">No pricing block in this response.</p>
                )}
              </div>

              <div className="fd-diff-section" role="region" aria-labelledby="diff-sec-metrics">
                <h4 className="fd-diff-section__title" id="diff-sec-metrics">
                  Cost and quality rollups
                </h4>
                {metrics ? (
                  <div className="fd-metric-grid">
                    <Metric
                      label="Cost / run (USD)"
                      baseline={num(metrics.baseline_cost_per_run_usd)}
                      candidate={num(metrics.candidate_cost_per_run_usd)}
                      delta={
                        typeof metrics.delta_cost_per_run_usd === "number"
                          ? `Δ ${num(metrics.delta_cost_per_run_usd)}${
                              typeof metrics.delta_cost_per_run_pct === "number"
                                ? ` (${metrics.delta_cost_per_run_pct >= 0 ? "+" : ""}${(metrics.delta_cost_per_run_pct * 100).toFixed(2)}% vs baseline)`
                                : ""
                            }`
                          : undefined
                      }
                    />
                    <Metric
                      label="Latency avg (ms)"
                      baseline={num(metrics.baseline_latency_ms_avg)}
                      candidate={num(metrics.candidate_latency_ms_avg)}
                      delta={
                        typeof metrics.delta_latency_ms_avg === "number"
                          ? `Δ ${num(metrics.delta_latency_ms_avg)} ms`
                          : undefined
                      }
                    />
                    <Metric
                      label="Error rate"
                      baseline={pct(metrics.baseline_error_rate)}
                      candidate={pct(metrics.candidate_error_rate)}
                      delta={
                        typeof metrics.delta_error_rate === "number"
                          ? `Δ ${pct(metrics.delta_error_rate)}`
                          : undefined
                      }
                    />
                  </div>
                ) : (
                  <p className="fd-muted fd-diff-section__body">No metrics block in this response.</p>
                )}
              </div>
            </div>
          </section>
          <JsonPanel title="Raw diff JSON" value={JSON.stringify(diffOut, null, 2)} defaultOpen={false} />
        </>
      ) : null}
    </>
  );
}
