import { useState } from "react";
import { fetchJson } from "../api";
import { Badge } from "../components/Badge";
import { JsonPanel } from "../components/JsonPanel";

type DiffJson = Record<string, unknown>;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function pickPolicy(data: DiffJson): { passed: boolean; reasons: string[] } | null {
  const p = data.policy;
  if (!isRecord(p)) return null;
  const passed = p.passed;
  const reasons = p.reasons;
  return {
    passed: passed === true,
    reasons: Array.isArray(reasons) ? reasons.filter((x): x is string => typeof x === "string") : [],
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
  const [diffBaseline, setDiffBaseline] = useState("");
  const [diffCandidate, setDiffCandidate] = useState("");
  const [diffWindow, setDiffWindow] = useState("7d");
  const [diffEnv, setDiffEnv] = useState("local");
  const [diffOut, setDiffOut] = useState<DiffJson | null>(null);
  const [diffErr, setDiffErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const runDiff = async () => {
    setDiffErr(null);
    setDiffOut(null);
    setBusy(true);
    try {
      const body = {
        baseline_release_id: diffBaseline.trim(),
        candidate_release_id: diffCandidate.trim(),
        window: diffWindow.trim(),
        environment: diffEnv.trim() || null,
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
      <div className="fd-page-head">
        <div>
          <h2 className="fd-page-title">Run diff</h2>
          <p className="fd-page-sub">
            Compare baseline vs candidate over a window. Same contract as{" "}
            <code className="fd-mono fd-mono--sm">flightdeck release diff</code>.
          </p>
        </div>
      </div>

      <section className="fd-card">
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
        </div>
      </section>

      {diffErr ? <p className="fd-alert fd-alert--error">{diffErr}</p> : null}

      {diffOut ? (
        <>
          <section className="fd-card">
            <div className="fd-card__head">
              <h3 className="fd-card__subtitle">Summary</h3>
              {policy ? (
                <div className="fd-inline">
                  <span className="fd-muted">Policy:</span>{" "}
                  <Badge tone={policy.passed ? "pass" : "fail"}>{policy.passed ? "PASS" : "FAIL"}</Badge>
                </div>
              ) : null}
            </div>
            {policy && policy.reasons.length > 0 ? (
              <ul className="fd-reasons">
                {policy.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : null}
            {samples ? (
              <p className="fd-muted fd-samples">
                Samples: baseline={num(samples.baseline_runs)} · candidate={num(samples.candidate_runs)} ·
                confidence: <strong>{String(samples.confidence ?? "—")}</strong>
                {typeof samples.confidence_reason === "string" ? ` — ${samples.confidence_reason}` : null}
              </p>
            ) : null}
            {pricing && pricing.warnings.length > 0 ? (
              <ul className="fd-alert fd-alert--warn fd-reasons">
                {pricing.warnings.map((w) => (
                  <li key={w}>Pricing warning: {w}</li>
                ))}
              </ul>
            ) : null}
            {pricing && pricing.hints.length > 0 ? (
              <ul className="fd-muted fd-reasons">
                {pricing.hints.map((h) => (
                  <li key={h}>Hint: {h}</li>
                ))}
              </ul>
            ) : null}
            {pricing && pricing.catalog && (pricing.catalog.enabled || pricing.catalog.warnings.length > 0) ? (
              <div className="fd-alert fd-alert--info">
                <strong>Catalog</strong>{" "}
                {pricing.catalog.enabled ? (
                  <>
                    v{pricing.catalog.version ?? "—"} · slots{" "}
                    <code className="fd-mono fd-mono--sm">{pricing.catalog.baselineSlot ?? "—"}</code> →{" "}
                    <code className="fd-mono fd-mono--sm">{pricing.catalog.candidateSlot ?? "—"}</code>
                    {pricing.catalog.baselineCost !== null &&
                    pricing.catalog.candidateCost !== null &&
                    pricing.catalog.deltaCost !== null ? (
                      <>
                        <br />
                        Comparable cost/run: {pricing.catalog.baselineCost.toFixed(6)} →{" "}
                        {pricing.catalog.candidateCost.toFixed(6)} (Δ {pricing.catalog.deltaCost >= 0 ? "+" : ""}
                        {pricing.catalog.deltaCost.toFixed(6)})
                      </>
                    ) : null}
                  </>
                ) : (
                  <span className="fd-muted">disabled or incomplete</span>
                )}
                {pricing.catalog.warnings.length > 0 ? (
                  <ul className="fd-reasons">
                    {pricing.catalog.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
            {pricing && pricing.changed ? (
              <p className="fd-alert fd-alert--warn">
                Pricing/model changed:{" "}
                <code className="fd-mono fd-mono--sm">
                  {pricing.baselineProvider}/{pricing.baselineVersion} {pricing.baselineModel}
                </code>{" "}
                →{" "}
                <code className="fd-mono fd-mono--sm">
                  {pricing.candidateProvider}/{pricing.candidateVersion} {pricing.candidateModel}
                </code>
                . Cost delta includes pricing and model assumption changes.
                {pricing.prices &&
                pricing.prices.baselineInput !== null &&
                pricing.prices.candidateInput !== null &&
                pricing.prices.baselineOutput !== null &&
                pricing.prices.candidateOutput !== null ? (
                  <>
                    <br />
                    Per-1k token prices: input{" "}
                    <code className="fd-mono fd-mono--sm">
                      {pricing.prices.baselineInput.toFixed(6)} → {pricing.prices.candidateInput.toFixed(6)}
                    </code>
                    , output{" "}
                    <code className="fd-mono fd-mono--sm">
                      {pricing.prices.baselineOutput.toFixed(6)} → {pricing.prices.candidateOutput.toFixed(6)}
                    </code>
                  </>
                ) : null}
              </p>
            ) : null}
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
            ) : null}
          </section>
          <JsonPanel title="Raw diff JSON" value={JSON.stringify(diffOut, null, 2)} defaultOpen={false} />
        </>
      ) : null}
    </>
  );
}
