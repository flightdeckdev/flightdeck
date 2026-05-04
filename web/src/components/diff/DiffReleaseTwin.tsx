import type { PricingInfo } from "./diffPayload";
import { pricingLine } from "./diffPayload";

export function DiffReleaseTwin({
  diffBaseline,
  diffCandidate,
  diffEnv,
  diffWindow,
  pricing,
}: {
  diffBaseline: string;
  diffCandidate: string;
  diffEnv: string;
  diffWindow: string;
  pricing: PricingInfo | null;
}) {
  const b = diffBaseline.trim();
  const c = diffCandidate.trim();
  return (
    <section className="fd-diff-twin" aria-labelledby="diff-twin-heading">
      <h3 className="fd-diff-twin__heading fd-sr-only" id="diff-twin-heading">
        Release comparison
      </h3>
      <div className="fd-diff-twin__meta fd-muted-xs">
        Environment <strong>{diffEnv.trim() || "—"}</strong> · Window <strong>{diffWindow.trim() || "—"}</strong>
      </div>
      <div className="fd-diff-twin__grid">
        <div className="fd-diff-twin__col">
          <span className="fd-diff-twin__label">Baseline (OLD)</span>
          <code className="fd-diff-twin__id fd-mono" title={b || undefined}>
            {b !== "" ? b : "—"}
          </code>
          <p className="fd-diff-twin__detail fd-muted fd-m-0 fd-mt-sm">{pricingLine(pricing, "baseline")}</p>
        </div>
        <div className="fd-diff-twin__arrow" aria-hidden>
          →
        </div>
        <div className="fd-diff-twin__col">
          <span className="fd-diff-twin__label">Candidate (NEW)</span>
          <code className="fd-diff-twin__id fd-mono" title={c || undefined}>
            {c !== "" ? c : "—"}
          </code>
          <p className="fd-diff-twin__detail fd-muted fd-m-0 fd-mt-sm">{pricingLine(pricing, "candidate")}</p>
        </div>
      </div>
    </section>
  );
}
