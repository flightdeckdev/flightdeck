import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "default" | "primary" | "ghost" | "danger";
type ButtonSize = "default" | "sm";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows spinner and disables the control; use `loadingLabel` for visible text while busy. */
  loading?: boolean;
  loadingLabel?: ReactNode;
};

function variantClass(variant: ButtonVariant): string {
  switch (variant) {
    case "primary":
      return "fd-btn--primary";
    case "ghost":
      return "fd-btn--ghost";
    case "danger":
      return "fd-btn--danger";
    default:
      return "";
  }
}

export function Button({
  variant = "default",
  size = "default",
  loading = false,
  loadingLabel,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  const { "aria-busy": ariaBusyFromCaller, ...domRest } = rest;

  const classes = [
    "fd-btn",
    variantClass(variant),
    size === "sm" ? "fd-btn--sm" : "",
    loading ? "fd-btn--loading" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  const label = loading && loadingLabel !== undefined ? loadingLabel : children;
  const ariaBusy = loading ? true : ariaBusyFromCaller;

  return (
    <button type={type} className={classes} disabled={disabled || loading} aria-busy={ariaBusy} {...domRest}>
      {loading ? <span className="fd-btn__spinner" aria-hidden="true" /> : null}
      <span className="fd-btn__label">{label}</span>
    </button>
  );
}
