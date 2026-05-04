/** Hash-router search helpers for deep-linking forms. */

export function pickTrimmedSearch(searchParams: URLSearchParams, key: string): string {
  const raw = searchParams.get(key);
  return raw !== null ? raw.trim() : "";
}

export function searchParamsFromRecord(rec: Record<string, string>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(rec)) {
    if (v !== "") sp.set(k, v);
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}
