import { Link } from "react-router-dom";
import { UI_READ_ONLY } from "../uiConfig";

type Step = {
  id: string;
  label: string;
  hint: string;
  to: string | null;
  end?: boolean;
  linkTitle: string;
};

const baseSteps: Step[] = [
  {
    id: "register",
    label: "Register",
    hint: "releases on this ledger",
    to: "/",
    end: true,
    linkTitle: "Overview — release registry and checksums (table may be empty until you verify releases via CLI).",
  },
  {
    id: "ingest",
    label: "Ingest",
    hint: "run evidence",
    to: "/runs",
    linkTitle:
      "Runs — paste a release ID from Overview (or CLI), then load runs. No auto-query until you choose a release.",
  },
  {
    id: "diff",
    label: "Diff & policy",
    hint: "compare + gate",
    to: "/diff",
    linkTitle:
      "Run diff — enter baseline and candidate release IDs, then run diff. Policy outcome appears in the same response.",
  },
  {
    id: "ship",
    label: "Promote & rollback",
    hint: "ledger actions",
    to: "/actions",
    linkTitle: "Promote and rollback — uses the same release and environment fields as the CLI HTTP API.",
  },
];

export function ReleaseLifecycleStrip() {
  const steps: Step[] = UI_READ_ONLY
    ? baseSteps.map((s) => (s.id === "ship" ? { ...s, to: null } : s))
    : baseSteps;

  return (
    <nav className="fd-lifecycle-strip" aria-label="Release governance workflow">
      <p className="fd-lifecycle-strip__intro">Control loop — where each step lives in this app.</p>
      <ol className="fd-lifecycle-strip__list">
        {steps.map((s, i) => (
          <li key={s.id} className="fd-lifecycle-strip__step">
            {i > 0 ? (
              <span className="fd-lifecycle-strip__arrow" aria-hidden="true">
                →
              </span>
            ) : null}
            {s.to ? (
              <Link to={s.to} end={s.end === true} className="fd-lifecycle-strip__link" title={s.linkTitle}>
                <span className="fd-lifecycle-strip__label">{s.label}</span>
                <span className="fd-lifecycle-strip__hint">{s.hint}</span>
              </Link>
            ) : (
              <span
                className="fd-lifecycle-strip__link fd-lifecycle-strip__link--static"
                title="Not available in read-only UI builds."
              >
                <span className="fd-lifecycle-strip__label">{s.label}</span>
                <span className="fd-lifecycle-strip__hint">{s.hint}</span>
              </span>
            )}
          </li>
        ))}
      </ol>
      <p className="fd-lifecycle-strip__note">
        Links always open the page. Deep links can prefill Diff, Runs, and Promote via URL query params; still run diff or load runs explicitly on those pages.
      </p>
    </nav>
  );
}
