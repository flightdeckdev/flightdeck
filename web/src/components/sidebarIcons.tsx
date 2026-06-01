import type { ReactNode, SVGProps } from "react";

const stroke = 1.75;

function shell(size: number, children: ReactNode, props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

/** Primary workspace / ledger */
export function IconOverview({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </>,
    props,
  );
}

/** Compare / diff */
export function IconDiff({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <path d="M12 3v18" />
      <path d="M4 8h7" />
      <path d="M13 16h7" />
      <path d="m6 5 2 2-2 2" />
      <path d="m18 15-2 2 2 2" />
    </>,
    props,
  );
}

/** Run events / list */
export function IconRuns({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <path d="M8 6h13" />
      <path d="M8 12h13" />
      <path d="M8 18h13" />
      <path d="M3 6h.01" />
      <path d="M3 12h.01" />
      <path d="M3 18h.01" />
    </>,
    props,
  );
}

/** Promote / release up */
export function IconPromote({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M12 16V8" />
      <path d="m9 11 3-3 3 3" />
    </>,
    props,
  );
}

/** Settings — sliders (complete paths; avoids truncated “gear” strokes at small sizes). */
export function IconSettings({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </>,
    props,
  );
}

/** Light theme (sun) */
export function IconSun({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </>,
    props,
  );
}

/** Dark theme (moon) */
export function IconMoon({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(size, <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />, props);
}

/** System / prefers-color-scheme (monitor) */
export function IconMonitor({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8" />
      <path d="M12 17v4" />
    </>,
    props,
  );
}

export function IconChevronLeft({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(size, <path d="m15 18-6-6 6-6" />, props);
}

export function IconChevronRight({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(size, <path d="m9 18 6-6-6-6" />, props);
}
