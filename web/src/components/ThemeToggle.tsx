import { useId } from "react";
import { useThemePreference } from "../context/ThemePreferenceContext";
import type { ThemePreference } from "../themeStorage";
import { IconMonitor, IconMoon, IconSun } from "./sidebarIcons";

const OPTIONS: { value: ThemePreference; label: string; Icon: typeof IconSun }[] = [
  { value: "light", label: "Light", Icon: IconSun },
  { value: "dark", label: "Dark", Icon: IconMoon },
  { value: "system", label: "System", Icon: IconMonitor },
];

/**
 * Theme picker for the sidebar Settings popover: inline “Theme” label + icon-only radios.
 */
export function ThemeToggle() {
  const themeLabelId = useId();
  const { preference, setPreference } = useThemePreference();

  return (
    <div className="fd-theme-toggle fd-theme-toggle--icons">
      <span id={themeLabelId} className="fd-theme-toggle__theme-label">
        Theme
      </span>
      <div
        className="fd-theme-toggle__icon-row"
        role="radiogroup"
        aria-labelledby={themeLabelId}
      >
        {OPTIONS.map(({ value, label, Icon }) => (
          <label key={value} className="fd-theme-toggle__icon-option" title={label}>
            <input
              type="radio"
              name="flightdeck-theme"
              value={value}
              className="fd-theme-toggle__input"
              checked={preference === value}
              onChange={() => setPreference(value)}
            />
            <span className="fd-theme-toggle__icon-wrap" aria-hidden="true">
              <Icon size={18} />
            </span>
            <span className="fd-sr-only">{label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
