import { DiffMetric } from "./diffPayload";
import type { PricingInfo } from "./diffPayload";
import { DiffPricingExpand } from "./DiffPricingExpand";

function num(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? String(v) : "—";
}

function pct(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(2)}%` : "—";
}

export function DiffChangeImpact({
  samples,
  metrics,
  pricing,
  pricingResetKey,
}: {
  samples: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  pricing: PricingInfo | null;
  pricingResetKey: number;
}) {
  return (
    <section className="fd-card" aria-labelledby="diff-impact-h">
      <div className="fd-card__head">
        <h3 className="fd-card__subtitle fd-m-0" id="diff-impact-h">
          Change impact
        </h3>
        <p className="fd-card__desc fd-m-0 fd-mt-sm">
          Evidence coverage, runtime rollups, and expandable pricing detail — causal drill-down stays here (no invented
          change rows until the API exposes them).
        </p>
      </div>
      <div className="fd-diff-stack">
        <div className="fd-diff-section" role="region" aria-labelledby="diff-sec-samples">
          <h4 className="fd-diff-section__title" id="diff-sec-samples">
            Sample coverage
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

        <div className="fd-diff-section" role="region" aria-labelledby="diff-sec-metrics">
          <h4 className="fd-diff-section__title" id="diff-sec-metrics">
            Cost and quality rollups
          </h4>
          {metrics ? (
            <div className="fd-metric-grid">
              <DiffMetric
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
              <DiffMetric
                label="Latency avg (ms)"
                baseline={num(metrics.baseline_latency_ms_avg)}
                candidate={num(metrics.candidate_latency_ms_avg)}
                delta={
                  typeof metrics.delta_latency_ms_avg === "number"
                    ? `Δ ${num(metrics.delta_latency_ms_avg)} ms`
                    : undefined
                }
              />
              <DiffMetric
                label="Error rate"
                baseline={pct(metrics.baseline_error_rate)}
                candidate={pct(metrics.candidate_error_rate)}
                delta={
                  typeof metrics.delta_error_rate === "number" ? `Δ ${pct(metrics.delta_error_rate)}` : undefined
                }
              />
            </div>
          ) : (
            <p className="fd-muted fd-diff-section__body">No metrics block in this response.</p>
          )}
        </div>

        {pricing ? (
          <DiffPricingExpand pricing={pricing} resetDetailKey={pricingResetKey} />
        ) : (
          <div className="fd-diff-section" role="region">
            <h4 className="fd-diff-section__title">Pricing &amp; model</h4>
            <p className="fd-muted fd-m-0">No pricing block in this response.</p>
          </div>
        )}
      </div>
    </section>
  );
}
