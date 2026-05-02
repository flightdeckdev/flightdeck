import { useEffect, useState } from "react";
import { fetchHealth, type HealthPayload } from "../api";
import { clientMutationTokenConfigured, UI_READ_ONLY } from "../uiConfig";

function resolveMutationAuth(data: HealthPayload): "bearer" | "loopback" | null {
  const m = data.mutation_auth;
  if (m === "bearer" || m === "loopback") return m;
  return null;
}

export function SecurityStatusBar() {
  const [auth, setAuth] = useState<"bearer" | "loopback" | null>(null);
  const [fetchErr, setFetchErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const h = await fetchHealth();
        if (!cancelled) {
          setAuth(resolveMutationAuth(h));
          setFetchErr(null);
        }
      } catch (e) {
        if (!cancelled) {
          setAuth(null);
          setFetchErr(String(e));
        }
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

  const serverLine =
    auth === "bearer"
      ? "Server requires an Authorization: Bearer token for promote and rollback."
      : "Server allows promote and rollback from loopback without a Bearer token.";

  const clientLine = hasClient
    ? "This UI build sends a client token (VITE_FLIGHTDECK_LOCAL_API_TOKEN is set)."
    : "This UI build does not send a client token (VITE_FLIGHTDECK_LOCAL_API_TOKEN unset).";

  return (
    <div className="fd-security-strip" role="status">
      {mismatch ? (
        <p className="fd-alert fd-alert--warn fd-security-strip__msg">
          Server expects a Bearer token for mutations, but this UI is not configured with{" "}
          <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code>. Promote and rollback
          requests will be rejected until the token matches{" "}
          <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code> on the server.
        </p>
      ) : (
        <p className="fd-alert fd-alert--info fd-security-strip__msg">
          <span className="fd-security-strip__line">{serverLine}</span>{" "}
          <span className="fd-security-strip__line">{clientLine}</span>
        </p>
      )}
    </div>
  );
}
