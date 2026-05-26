import { useEffect, useState } from "react";
import { fetchHealth, type HealthPayload } from "../api";
import { clientMutationTokenConfigured, UI_READ_ONLY } from "../uiConfig";
import { StatusChip } from "./StatusChip";

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
        <div className="fd-status-chip-row">
          <StatusChip label="UI mode" value="Read-only" tone="info" />
        </div>
        <p className="fd-security-strip__detail">
          Promote and rollback navigation is disabled (
          <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_UI_READ_ONLY</code>).
        </p>
      </div>
    );
  }

  if (healthLoading) {
    return (
      <div className="fd-security-strip" role="status" aria-busy="true" aria-live="polite">
        <span className="fd-sr-only">Checking server security</span>
        <div className="fd-status-chip-row">
          <StatusChip label="API security" value="Checking…" tone="neutral" />
        </div>
        <span className="fd-skeleton fd-skeleton--w75 fd-security-strip__skeleton" />
      </div>
    );
  }

  if (fetchErr) {
    return (
      <div className="fd-security-strip" role="status">
        <p className="fd-alert fd-alert--warn fd-security-strip__msg">
          Could not load security mode from <code className="fd-mono fd-mono--sm">/health</code>: {fetchErr}
        </p>
      </div>
    );
  }

  if (auth === null) {
    return null;
  }

  const mutationTone = auth === "bearer" ? "info" : "pass";
  const readTone = readAuth === "bearer" ? "info" : "neutral";
  const clientTone = hasClient ? "pass" : mismatch ? "warn" : "neutral";

  return (
    <div className="fd-security-strip" role="status">
      <div className="fd-status-chip-row">
        <StatusChip
          label="Writes"
          value={auth === "bearer" ? "Bearer required" : "Loopback open"}
          tone={mutationTone}
        />
        <StatusChip
          label="Reads"
          value={readAuth === "bearer" ? "Bearer required" : "Open"}
          tone={readTone}
        />
        <StatusChip
          label="UI token"
          value={hasClient ? "Configured" : "Not set"}
          tone={clientTone}
        />
      </div>
      {mismatch ? (
        <p className="fd-alert fd-alert--warn fd-security-strip__detail">
          Server expects <code className="fd-mono fd-mono--sm">Authorization: Bearer</code> for writes and reads, but{" "}
          <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code> is unset in this UI build. Set it
          to match <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code> on the server.
        </p>
      ) : auth === "bearer" && hasClient ? (
        <p className="fd-security-strip__detail fd-muted">
          Confirm the UI token matches the server&apos;s <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code>.
        </p>
      ) : (
        <p className="fd-security-strip__detail fd-muted">
          Ingest, promote, and rollback follow the write mode above. Diff stays unauthenticated.
        </p>
      )}
    </div>
  );
}
