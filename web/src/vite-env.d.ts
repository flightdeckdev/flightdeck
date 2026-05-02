/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** When set, sent as `Authorization: Bearer …` on API calls (matches server `FLIGHTDECK_LOCAL_API_TOKEN`). */
  readonly VITE_FLIGHTDECK_LOCAL_API_TOKEN?: string;
  /** Set to the string `true` to hide promote/rollback navigation and routes. */
  readonly VITE_FLIGHTDECK_UI_READ_ONLY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
