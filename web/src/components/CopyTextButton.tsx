import { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  label: string;
  value: string;
  /** Short label for the control (e.g. "Copy ID"). */
  buttonText?: string;
  className?: string;
  /** Optional hook for e2e (first matching control on page). */
  testId?: string;
};

export function CopyTextButton({ label, value, buttonText = "Copy", className, testId }: Props) {
  const [status, setStatus] = useState<"idle" | "ok" | "err">("idle");
  const timeoutsRef = useRef<ReturnType<typeof window.setTimeout>[]>([]);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      for (const id of timeoutsRef.current) {
        window.clearTimeout(id);
      }
      timeoutsRef.current = [];
    };
  }, []);

  const scheduleReset = useCallback((ms: number) => {
    const id = window.setTimeout(() => {
      timeoutsRef.current = timeoutsRef.current.filter((t) => t !== id);
      if (mountedRef.current) setStatus("idle");
    }, ms);
    timeoutsRef.current.push(id);
  }, []);

  const copyViaExecCommand = useCallback(() => {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  }, [value]);

  const copy = useCallback(async () => {
    if (!mountedRef.current) return;
    setStatus("idle");
    try {
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(value);
        } catch {
          // Headless / insecure contexts often deny clipboard; execCommand still works for UX tests.
          if (!copyViaExecCommand()) throw new Error("clipboard unavailable");
        }
      } else if (!copyViaExecCommand()) {
        throw new Error("copy unsupported");
      }
      if (!mountedRef.current) return;
      setStatus("ok");
      scheduleReset(2000);
    } catch {
      if (!mountedRef.current) return;
      setStatus("err");
      scheduleReset(2500);
    }
  }, [copyViaExecCommand, scheduleReset]);

  const msg =
    status === "ok" ? "Copied." : status === "err" ? "Copy failed." : `${label} — ${buttonText}`;

  return (
    <button
      type="button"
      className={className ?? "fd-btn fd-btn--ghost fd-copy-btn"}
      title={`${label}: ${value}`}
      aria-label={msg}
      data-testid={testId}
      onClick={() => void copy()}
    >
      {status === "ok" ? "Copied" : status === "err" ? "Failed" : buttonText}
    </button>
  );
}
