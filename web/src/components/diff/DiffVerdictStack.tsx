import type { PolicyView } from "./diffPayload";

export function DiffVerdictStack({ policy }: { policy: PolicyView | null }) {
  return (
    <>
      {policy && !policy.passed && policy.reasons.length > 0 ? (
        <div className="fd-diff-block-strip" role="status">
          <strong>Blocked:</strong> <span>{policy.reasons[0]}</span>
          {policy.reasons.length > 1 ? (
            <span className="fd-muted-inline fd-ml-sm">
              (+{policy.reasons.length - 1} more in policy evaluation)
            </span>
          ) : null}
        </div>
      ) : null}

      {policy ? (
        <div
          className={`fd-diff-verdict-strip ${policy.passed ? "fd-diff-verdict-strip--pass" : "fd-diff-verdict-strip--fail"}`}
          role="status"
          aria-live="polite"
        >
          {policy.passed
            ? "Policy PASS — candidate may proceed if you accept the impact below."
            : "Policy FAIL — do not promote this candidate for this evaluation."}
        </div>
      ) : (
        <div className="fd-alert fd-alert--warn" role="status">
          <strong>No policy block</strong> in this diff response — confirm server version and request payload before
          treating the outcome as gated.
        </div>
      )}
    </>
  );
}
