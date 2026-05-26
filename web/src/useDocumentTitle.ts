import { useEffect } from "react";

const TITLE_SUFFIX = " · FlightDeck";

/**
 * Sets `document.title` for the active route (browser tab / history).
 */
export function useDocumentTitle(pageTitle: string) {
  useEffect(() => {
    const trimmed = pageTitle.trim();
    document.title = trimmed.endsWith("FlightDeck") ? trimmed : `${trimmed}${TITLE_SUFFIX}`;
  }, [pageTitle]);
}
