/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** When set, sent as `Authorization: Bearer …` on API calls (matches server `FLIGHTDECK_LOCAL_API_TOKEN`). */
  readonly VITE_FLIGHTDECK_LOCAL_API_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
