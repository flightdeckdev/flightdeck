import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type TimelineRefreshValue = {
  /** Increments when server-side timeline data may have changed (e.g. promote/rollback). */
  generation: number;
  /** Call after a successful mutation that affects releases, promoted pointers, or actions. */
  notifyTimelineMutated: () => void;
};

const TimelineRefreshContext = createContext<TimelineRefreshValue | null>(null);

export function TimelineRefreshProvider({ children }: { children: ReactNode }) {
  const [generation, setGeneration] = useState(0);
  const notifyTimelineMutated = useCallback(() => {
    setGeneration((g) => g + 1);
  }, []);
  const value = useMemo(
    () => ({ generation, notifyTimelineMutated }),
    [generation, notifyTimelineMutated],
  );
  return <TimelineRefreshContext.Provider value={value}>{children}</TimelineRefreshContext.Provider>;
}

export function useTimelineRefresh(): TimelineRefreshValue {
  const ctx = useContext(TimelineRefreshContext);
  if (!ctx) {
    throw new Error("useTimelineRefresh must be used within TimelineRefreshProvider");
  }
  return ctx;
}
