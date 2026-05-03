import { useId } from "react";
import { useThemePreference } from "../context/ThemePreferenceContext";
import type { ThemePreference } from "../themeStorage";

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export function ThemeToggle({ variant = "default" }: { variant?: "default" | "settings" }) {
  const legendId = useId();
  const { preference, setPreference } = useThemePreference();
  const fs = variant === "settings" ? "fd-theme-toggle fd-theme-toggle--settings" : "fd-theme-toggle";

  return (
    <fieldset className={fs} aria-labelledby={legendId}>
      <legend id={legendId} className="fd-theme-toggle__legend">
        Appearance
      </legend>
      <div className="fd-theme-toggle__options">
        {OPTIONS.map(({ value, label }) => (
          <label key={value} className="fd-theme-toggle__label">
            <input
              type="radio"
              name="flightdeck-theme"
              value={value}
              className="fd-theme-toggle__input"
              checked={preference === value}
              onChange={() => setPreference(value)}
            />
            <span className="fd-theme-toggle__text">{label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
