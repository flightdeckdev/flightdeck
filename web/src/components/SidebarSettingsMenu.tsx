import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ThemeToggle } from "./ThemeToggle";
import { IconSettings } from "./sidebarIcons";

const POPOVER_WIDTH = 248;
const POPOVER_ESTIMATE_H = 220;

function positionPopover(trigger: HTMLElement) {
  const r = trigger.getBoundingClientRect();
  const gap = 8;
  let left = r.right + gap;
  if (left + POPOVER_WIDTH > window.innerWidth - gap) {
    left = Math.max(gap, r.left - POPOVER_WIDTH - gap);
  }
  let top = r.top;
  if (top + POPOVER_ESTIMATE_H > window.innerHeight - gap) {
    top = Math.max(gap, window.innerHeight - POPOVER_ESTIMATE_H - gap);
  }
  top = Math.max(gap, Math.min(top, window.innerHeight - gap));
  return { top, left };
}

export function SidebarSettingsMenu({ sidebarCollapsed }: { sidebarCollapsed: boolean }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const close = useCallback(() => {
    setOpen(false);
    queueMicrotask(() => triggerRef.current?.focus());
  }, []);

  const reposition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    setCoords(positionPopover(el));
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    reposition();
  }, [open, sidebarCollapsed, reposition]);

  useEffect(() => {
    if (!open) return;
    const onResize = () => reposition();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [open, reposition]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [open, close]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent | PointerEvent) => {
      const t = e.target as Node;
      if (panelRef.current?.contains(t) || triggerRef.current?.contains(t)) return;
      close();
    };
    document.addEventListener("pointerdown", onPointer, true);
    return () => document.removeEventListener("pointerdown", onPointer, true);
  }, [open, close]);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => {
      const first = panelRef.current?.querySelector<HTMLElement>(
        'input[type="radio"], button:not([disabled])',
      );
      first?.focus();
    }, 0);
    return () => window.clearTimeout(t);
  }, [open]);

  const portal =
    open && typeof document !== "undefined"
      ? createPortal(
          <>
            <div className="fd-settings-popover-backdrop" aria-hidden="true" />
            <div
              ref={panelRef}
              id="sidebar-settings-popover"
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              className="fd-settings-popover"
              style={{ top: coords.top, left: coords.left, width: POPOVER_WIDTH }}
            >
              <div className="fd-settings-popover__head" id={titleId}>
                Settings
              </div>
              <p className="fd-settings-popover__hint">Saved in this browser only.</p>
              <div className="fd-settings-popover__body">
                <ThemeToggle />
              </div>
            </div>
          </>,
          document.body,
        )
      : null;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        data-testid="sidebar-settings-trigger"
        className={`fd-nav__link fd-nav__link--button${open ? " fd-nav__link--active" : ""}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls={open ? "sidebar-settings-popover" : undefined}
        title="Settings"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="fd-nav__glyph" aria-hidden="true">
          <IconSettings />
        </span>
        <span className="fd-nav__label">Settings</span>
      </button>
      {portal}
    </>
  );
}
