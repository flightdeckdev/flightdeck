import { NavLink, Outlet } from "react-router-dom";
import { TimelineRefreshProvider } from "../context/TimelineRefreshContext";
import { SecurityStatusBar } from "./SecurityStatusBar";
import { UI_READ_ONLY } from "../uiConfig";

const navCls = ({ isActive }: { isActive: boolean }) =>
  `fd-nav__link${isActive ? " fd-nav__link--active" : ""}`;

export function AppShell() {
  return (
    <TimelineRefreshProvider>
      <div className="fd-shell">
        <header className="fd-header">
          <div className="fd-header__brand">
            <h1 className="fd-header__title">FlightDeck</h1>
            <p className="fd-header__tagline">Diffs, evidence, policy gates</p>
          </div>
          <nav className="fd-nav" aria-label="Primary">
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
        </header>
        <SecurityStatusBar />
        <main className="fd-main">
          <Outlet />
        </main>
      </div>
    </TimelineRefreshProvider>
  );
}
