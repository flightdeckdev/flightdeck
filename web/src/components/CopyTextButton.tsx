import { useCallback, useState } from "react";

type Props = {
  label: string;
  value: string;
  /** Short label for the control (e.g. "Copy ID"). */
  buttonText?: string;
  className?: string;
};

export function CopyTextButton({ label, value, buttonText = "Copy", className }: Props) {
  const [status, setStatus] = useState<"idle" | "ok" | "err">("idle");

  const copy = useCallback(async () => {
    setStatus("idle");
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setStatus("ok");
      window.setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("err");
      window.setTimeout(() => setStatus("idle"), 2500);
    }
  }, [value]);

  const msg =
    status === "ok" ? "Copied." : status === "err" ? "Copy failed." : `${label} — ${buttonText}`;

  return (
    <button
      type="button"
      className={className ?? "fd-btn fd-btn--ghost fd-copy-btn"}
      title={`${label}: ${value}`}
      aria-label={msg}
      onClick={() => void copy()}
    >
      {status === "ok" ? "Copied" : status === "err" ? "Failed" : buttonText}
    </button>
  );
}
