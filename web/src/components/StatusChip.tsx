import type { ReactNode } from "react";

type StatusChipTone = "neutral" | "pass" | "warn" | "fail" | "info";

export function StatusChip({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  tone?: StatusChipTone;
}) {
  return (
    <span className={`fd-status-chip fd-status-chip--${tone}`}>
      <span className="fd-status-chip__label">{label}</span>
      <span className="fd-status-chip__value">{value}</span>
    </span>
  );
}
