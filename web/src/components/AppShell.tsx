import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";
import { TimelineRefreshProvider } from "../context/TimelineRefreshContext";
import { flightdeckMarkUrl } from "../branding";
import { readSidebarCollapsed, writeSidebarCollapsed } from "../sidebarStorage";
import { SecurityStatusBar } from "./SecurityStatusBar";
import {
  IconChevronLeft,
  IconChevronRight,
  IconDiff,
  IconOverview,
  IconPromote,
  IconRuns,
} from "./sidebarIcons";
import { SidebarNavLink } from "./SidebarNavLink";
import { SidebarSettingsMenu } from "./SidebarSettingsMenu";
import { UI_READ_ONLY } from "../uiConfig";

function skipToMain() {
  document.getElementById("main-content")?.focus({ preventScroll: false });
}

export function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarCollapsed);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      writeSidebarCollapsed(next);
      return next;
    });
  }, []);

  return (
    <TimelineRefreshProvider>
      <div className="fd-shell">
        <button type="button" className="fd-skip-link" onClick={skipToMain}>
          Skip to main content
        </button>
        <aside
          className={`fd-sidebar${sidebarCollapsed ? " fd-sidebar--collapsed" : ""}`}
          aria-label="FlightDeck main navigation"
        >
          <div className="fd-sidebar__head">
            <div className="fd-sidebar__brand">
              <div className="fd-sidebar__brand-top">
                <div className="fd-sidebar__logo-wrap">
                  <img
                    className="fd-sidebar__logo"
                    src={flightdeckMarkUrl}
                    alt=""
                    decoding="async"
                  />
                </div>
                <h1 className="fd-sidebar__title">
                  <span className="fd-sidebar__title-text">FlightDeck</span>
                </h1>
              </div>
              <p className="fd-sidebar__tagline">Release safety ledger</p>
            </div>
            <button
              type="button"
              className="fd-sidebar__collapse"
              onClick={toggleSidebar}
              aria-expanded={!sidebarCollapsed}
              aria-controls="sidebar-primary-nav sidebar-footer-nav"
              title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {sidebarCollapsed ? <IconChevronRight size={18} /> : <IconChevronLeft size={18} />}
              <span className="fd-sr-only">{sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}</span>
            </button>
          </div>
          <div className="fd-sidebar__nav-stack">
            <nav id="sidebar-primary-nav" className="fd-sidebar__nav fd-sidebar__nav--primary" aria-label="Primary">
              <SidebarNavLink to="/" end label="Overview" icon={<IconOverview />} />
              <SidebarNavLink to="/diff" label="Diff" icon={<IconDiff />} />
              <SidebarNavLink to="/runs" label="Runs" icon={<IconRuns />} />
              {UI_READ_ONLY ? null : <SidebarNavLink to="/actions" label="Promote" icon={<IconPromote />} />}
            </nav>
            <nav
              id="sidebar-footer-nav"
              className="fd-sidebar__nav fd-sidebar__nav--footer"
              aria-label="Settings and appearance"
            >
              <SidebarSettingsMenu sidebarCollapsed={sidebarCollapsed} />
            </nav>
          </div>
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
