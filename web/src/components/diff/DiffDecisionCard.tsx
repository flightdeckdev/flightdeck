import { Link } from "react-router-dom";
import type { PolicyView } from "./diffPayload";

export function DiffDecisionCard({
  policy,
  promoteSearch,
}: {
  policy: PolicyView | null;
  promoteSearch: string;
}) {
  return (
    <section className="fd-card fd-decision-card" aria-labelledby="diff-decision-h">
      <div className="fd-card__head">
        <h3 className="fd-card__subtitle fd-m-0" id="diff-decision-h">
          Decision
        </h3>
        <p className="fd-card__desc fd-m-0 fd-mt-sm">
          {policy === null
            ? "Run diff again after fixing the payload or server configuration."
            : policy.passed
              ? "Gate passed for this baseline, candidate, window, and environment. Next: promote from Actions if operational checks agree."
              : "Gate failed — resolve policy findings or choose a different candidate/baseline before promoting."}
        </p>
      </div>
      {policy?.passed === true && promoteSearch !== "" ? (
        <div className="fd-actions fd-mt-md">
          <Link className="fd-btn fd-btn--primary" to={{ pathname: "/actions", search: promoteSearch }}>
            Continue to promote
          </Link>
          <span className="fd-muted-inline fd-grow-soft">
            Candidate release and window/environment are prefilled; reason is still required on Actions.
          </span>
        </div>
      ) : null}
    </section>
  );
}
