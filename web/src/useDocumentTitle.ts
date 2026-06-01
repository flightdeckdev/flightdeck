import { useEffect } from "react";

const TITLE_SUFFIX = " · FlightDeck";
const SUFFIX_RE = / · FlightDeck$/;

/**
 * Sets `document.title` for the active route (browser tab / history).
 */
export function useDocumentTitle(pageTitle: string) {
  useEffect(() => {
    const trimmed = pageTitle.trim();
    if (!trimmed) return;
    document.title = trimmed === "FlightDeck" || SUFFIX_RE.test(trimmed) ? trimmed : `${trimmed}${TITLE_SUFFIX}`;
  }, [pageTitle]);
}
