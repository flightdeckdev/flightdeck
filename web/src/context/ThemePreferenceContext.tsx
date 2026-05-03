import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  applyDocumentTheme,
  readStoredThemePreference,
  resolveEffectiveTheme,
  writeStoredThemePreference,
  type ThemePreference,
} from "../themeStorage";

type ThemePreferenceContextValue = {
  preference: ThemePreference;
  setPreference: (next: ThemePreference) => void;
  effective: "light" | "dark";
};

const ThemePreferenceContext = createContext<ThemePreferenceContextValue | null>(null);

export function ThemePreferenceProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => readStoredThemePreference());
  const [effective, setEffective] = useState<"light" | "dark">(() =>
    resolveEffectiveTheme(readStoredThemePreference()),
  );

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    writeStoredThemePreference(next);
  }, []);

  useEffect(() => {
    const eff = resolveEffectiveTheme(preference);
    setEffective(eff);
    applyDocumentTheme(eff);
  }, [preference]);

  useEffect(() => {
    if (preference !== "system") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const eff = resolveEffectiveTheme("system");
      setEffective(eff);
      applyDocumentTheme(eff);
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [preference]);

  const value = useMemo(
    () => ({ preference, setPreference, effective }),
    [preference, setPreference, effective],
  );

  return <ThemePreferenceContext.Provider value={value}>{children}</ThemePreferenceContext.Provider>;
}

export function useThemePreference(): ThemePreferenceContextValue {
  const v = useContext(ThemePreferenceContext);
  if (!v) {
    throw new Error("useThemePreference must be used within ThemePreferenceProvider");
  }
  return v;
}
