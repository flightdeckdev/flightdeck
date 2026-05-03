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

/** Settings / gear */
export function IconSettings({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return shell(
    size,
    <>
      <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H12a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V12c0 .62-.24 1.18-.63 1.59" />
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
