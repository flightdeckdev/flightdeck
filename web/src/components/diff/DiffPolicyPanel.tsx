import { Badge } from "../Badge";
import type { PolicyView } from "./diffPayload";

export function DiffPolicyPanel({ policy }: { policy: PolicyView }) {
  return (
    <section className="fd-card fd-policy-panel" aria-labelledby="diff-policy-h">
      <div className="fd-card__head fd-card__head--row">
        <h3 className="fd-card__subtitle fd-m-0" id="diff-policy-h">
          Policy evaluation
        </h3>
        <Badge tone={policy.passed ? "pass" : "fail"}>{policy.passed ? "PASS" : "FAIL"}</Badge>
      </div>
      {policy.evaluatedAt ? (
        <p className="fd-muted fd-m-0 fd-mb-md">
          evaluated_at <span className="fd-mono fd-mono--sm">{policy.evaluatedAt}</span>
        </p>
      ) : null}
      {policy.reasons.length > 0 ? (
        <ul className="fd-reasons fd-mt-0 fd-mb-0">
          {policy.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : (
        <p className="fd-muted fd-m-0">
          {policy.passed
            ? "No constraint messages returned (pass with empty reasons)."
            : "No reasons listed — inspect raw JSON and server policy."}
        </p>
      )}
    </section>
  );
}
