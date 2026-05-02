import { useId, useState } from "react";

type Props = {
  title?: string;
  value: string;
  defaultOpen?: boolean;
};

export function JsonPanel({ title = "Raw JSON", value, defaultOpen = false }: Props) {
  const id = useId();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="fd-json-panel">
      <button
        type="button"
        className="fd-json-panel__toggle"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="fd-json-panel__chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
        {title}
      </button>
      {open ? (
        <pre id={id} className="fd-json-panel__pre">
          {value}
        </pre>
      ) : null}
    </div>
  );
}
