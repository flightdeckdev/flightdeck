import { NavLink, Outlet } from "react-router-dom";
import { TimelineRefreshProvider } from "../context/TimelineRefreshContext";
import { SecurityStatusBar } from "./SecurityStatusBar";
import { UI_READ_ONLY } from "../uiConfig";

const navCls = ({ isActive }: { isActive: boolean }) =>
  `fd-nav__link${isActive ? " fd-nav__link--active" : ""}`;

function skipToMain() {
  document.getElementById("main-content")?.focus({ preventScroll: false });
}

export function AppShell() {
  return (
    <TimelineRefreshProvider>
      <div className="fd-shell">
        <button type="button" className="fd-skip-link" onClick={skipToMain}>
          Skip to main content
        </button>
        <aside className="fd-sidebar" aria-label="Application">
          <div className="fd-sidebar__brand">
            <h1 className="fd-sidebar__title">FlightDeck</h1>
            <p className="fd-sidebar__tagline">Diffs, evidence, policy gates</p>
          </div>
          <nav className="fd-sidebar__nav" aria-label="Primary">
            <NavLink to="/" end className={navCls}>
              Overview
            </NavLink>
            <NavLink to="/diff" className={navCls}>
              Diff
            </NavLink>
            <NavLink to="/runs" className={navCls}>
              Runs
            </NavLink>
            {UI_READ_ONLY ? null : (
              <NavLink to="/actions" className={navCls}>
                Promote
              </NavLink>
            )}
          </nav>
        </aside>
        <div className="fd-shell__content">
          <SecurityStatusBar />
          <main id="main-content" className="fd-main" tabIndex={-1}>
            <Outlet />
          </main>
        </div>
      </div>
    </TimelineRefreshProvider>
  );
}