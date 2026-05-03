import { useEffect, useState } from "react";
import { fetchHealth, type HealthPayload } from "../api";
import { clientMutationTokenConfigured, UI_READ_ONLY } from "../uiConfig";

function resolveMutationAuth(data: HealthPayload): "bearer" | "loopback" | null {
  const m = data.mutation_auth;
  if (m === "bearer" || m === "loopback") return m;
  return null;
}

function resolveReadAuth(data: HealthPayload): "bearer" | "open" | null {
  const r = data.read_auth;
  if (r === "bearer" || r === "open") return r;
  return null;
}

export function SecurityStatusBar() {
  const [auth, setAuth] = useState<"bearer" | "loopback" | null>(null);
  const [readAuth, setReadAuth] = useState<"bearer" | "open" | null>(null);
  const [fetchErr, setFetchErr] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setHealthLoading(true);
      try {
        const h = await fetchHealth();
        if (!cancelled) {
          setAuth(resolveMutationAuth(h));
          setReadAuth(resolveReadAuth(h));
          setFetchErr(null);
        }
      } catch (e) {
        if (!cancelled) {
          setAuth(null);
          setReadAuth(null);
          setFetchErr(String(e));
        }
      } finally {
        if (!cancelled) setHealthLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const hasClient = clientMutationTokenConfigured();
  const mismatch = auth === "bearer" && !hasClient;

  if (UI_READ_ONLY) {
    return (
      <div className="fd-security-strip" role="status">
        <p className="fd-alert fd-alert--info fd-security-strip__msg">
          Read-only UI: navigation to promote and rollback is disabled (
          <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_UI_READ_ONLY</code>).
        </p>
      </div>
    );
  }

  if (healthLoading) {
    return (
      <div className="fd-security-strip" role="status" aria-busy="true" aria-live="polite">
        <span className="fd-sr-only">Checking server security</span>
        <p className="fd-muted fd-security-strip__msg fd-security-strip__loading-line">
          Checking <code className="fd-mono fd-mono--sm">/health</code> for API security…
        </p>
        <span className="fd-skeleton fd-skeleton--w75 fd-security-strip__skeleton" />
      </div>
    );
  }

  if (fetchErr) {
    return (
      <div className="fd-security-strip" role="status">
        <p className="fd-alert fd-alert--warn fd-security-strip__msg">
          Could not load server security mode from <code className="fd-mono fd-mono--sm">/health</code>
          : {fetchErr}
        </p>
      </div>
    );
  }

  if (auth === null) {
    return null;
  }

  const readLine =
    readAuth === "bearer"
      ? "GET /v1/* read APIs require the same Bearer token."
      : "GET /v1/* read APIs are open (no Bearer) while the server has no API token configured.";

  const serverLine =
    auth === "bearer"
      ? "Server requires an Authorization: Bearer token for ledger writes (ingest, promote, rollback)."
      : "Server allows ledger writes from loopback without a Bearer token.";

  const clientLine = hasClient
    ? "This UI build sends a client token (VITE_FLIGHTDECK_LOCAL_API_TOKEN is set)."
    : "This UI build does not send a client token (VITE_FLIGHTDECK_LOCAL_API_TOKEN unset).";

  if (auth === "bearer" && hasClient) {
    return (
      <div className="fd-security-strip" role="status">
        <p className="fd-muted fd-security-strip__msg">
          Bearer API: <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code> is set —
          confirm it matches the server&apos;s{" "}
          <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code> (writes and{" "}
          <code className="fd-mono fd-mono--sm">GET /v1/*</code> when the server uses a token).
        </p>
      </div>
    );
  }

  return (
    <div className="fd-security-strip" role="status">
      {mismatch ? (
        <p className="fd-alert fd-alert--warn fd-security-strip__msg">
          Server expects a Bearer token for writes and read APIs, but this UI is not configured with{" "}
          <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code>. Requests will be rejected
          until the token matches{" "}
          <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code> on the server.
        </p>
      ) : (
        <p className="fd-alert fd-alert--info fd-security-strip__msg">
          <span className="fd-security-strip__line">{serverLine}</span>{" "}
          <span className="fd-security-strip__line">{readLine}</span>{" "}
          <span className="fd-security-strip__line">{clientLine}</span>
        </p>
      )}
    </div>
  );
}
