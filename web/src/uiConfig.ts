/** When `true`, hide promote/rollback routes and navigation (demo / shared-screen mode). */
export const UI_READ_ONLY = import.meta.env.VITE_FLIGHTDECK_UI_READ_ONLY === "true";

export function clientMutationTokenConfigured(): boolean {
  const t = import.meta.env.VITE_FLIGHTDECK_LOCAL_API_TOKEN;
  return typeof t === "string" && t.trim().length > 0;
}
