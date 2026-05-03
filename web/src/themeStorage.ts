/** Persisted UI appearance; synced to `document.documentElement.dataset.theme`. */
export const THEME_STORAGE_KEY = "flightdeck-theme";

export type ThemePreference = "light" | "dark" | "system";

export function isThemePreference(v: string | null): v is ThemePreference {
  return v === "light" || v === "dark" || v === "system";
}

/** Default matches pre-theming behavior (light chrome). */
export function readStoredThemePreference(): ThemePreference {
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY);
    if (isThemePreference(v)) return v;
  } catch {
    /* private mode */
  }
  return "light";
}

export function writeStoredThemePreference(pref: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, pref);
  } catch {
    /* ignore */
  }
}

export function resolveEffectiveTheme(pref: ThemePreference): "light" | "dark" {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref;
}

export function applyDocumentTheme(effective: "light" | "dark"): void {
  document.documentElement.dataset.theme = effective;
  document.documentElement.style.colorScheme = effective;
}
