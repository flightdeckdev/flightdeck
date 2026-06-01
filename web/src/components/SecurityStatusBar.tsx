import { useEffect, useState } from "react";
import { fetchHealth, type HealthPayload } from "../api";
import { clientMutationTokenConfigured, UI_READ_ONLY } from "../uiConfig";
import { StatusChip } from "./StatusChip";

type MutationAuthResolved = "bearer" | "loopback" | "unknown";
type ReadAuthResolved = "bearer" | "open" | "unknown";

function resolveMutationAuth(data: HealthPayload): MutationAuthResolved {
  const m = data.mutation_auth;
  if (m === "bearer" || m === "loopback") return m;
  return "unknown";
}

function resolveReadAuth(data: HealthPayload): ReadAuthResolved {
  const r = data.read_auth;
  if (r === "bearer" || r === "open") return r;
  return "unknown";
}

export function SecurityStatusBar() {
  const [mutationAuth, setMutationAuth] = useState<MutationAuthResolved | null>(null);
  const [readAuth, setReadAuth] = useState<ReadAuthResolved | null>(null);
  const [fetchErr, setFetchErr] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    if (UI_READ_ONLY) {
      setHealthLoading(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      setHealthLoading(true);
      try {
        const h = await fetchHealth();
        if (!cancelled) {
          setMutationAuth(resolveMutationAuth(h));
          setReadAuth(resolveReadAuth(h));
          setFetchErr(null);
        }
      } catch (e) {
        if (!cancelled) {
          setMutationAuth(null);
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
  const mismatch = mutationAuth === "bearer" && !hasClient;

  if (UI_READ_ONLY) {
    return (
      <div className="fd-security-strip" role="status" data-testid="security-strip">
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
      <div className="fd-security-strip" role="status" aria-busy="true" aria-live="polite" data-testid="security-strip">
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
      <div className="fd-security-strip" role="status" data-testid="security-strip">
        <p className="fd-alert fd-alert--warn fd-security-strip__msg">
          Could not load security mode from <code className="fd-mono fd-mono--sm">/health</code>: {fetchErr}
        </p>
      </div>
    );
  }

  if (mutationAuth === null || readAuth === null) {
    return (
      <div className="fd-security-strip" role="status" data-testid="security-strip">
        <p className="fd-alert fd-alert--warn fd-security-strip__msg">
          Security mode from <code className="fd-mono fd-mono--sm">/health</code> is unavailable.
        </p>
      </div>
    );
  }

  const writeValue =
    mutationAuth === "bearer" ? "Bearer required" : mutationAuth === "loopback" ? "Loopback open" : "Unknown";
  const writeTone =
    mutationAuth === "bearer" ? "info" : mutationAuth === "loopback" ? "pass" : "warn";

  const readValue =
    readAuth === "bearer" ? "Bearer required" : readAuth === "open" ? "Open" : "Unknown";
  const readTone = readAuth === "bearer" ? "info" : readAuth === "open" ? "neutral" : "warn";

  const clientTone = hasClient ? "pass" : mismatch ? "warn" : "neutral";

  const contractDrift = mutationAuth === "unknown" || readAuth === "unknown";

  return (
    <div className="fd-security-strip" role="status" data-testid="security-strip">
      <div className="fd-status-chip-row">
        <StatusChip label="Writes" value={writeValue} tone={writeTone} />
        <StatusChip label="Reads" value={readValue} tone={readTone} />
        <StatusChip
          label="UI token"
          value={hasClient ? "Configured" : "Not set"}
          tone={clientTone}
        />
      </div>
      {contractDrift ? (
        <p className="fd-alert fd-alert--warn fd-security-strip__detail">
          <code className="fd-mono fd-mono--sm">/health</code> omitted or returned an unexpected{" "}
          <code className="fd-mono fd-mono--sm">mutation_auth</code> / <code className="fd-mono fd-mono--sm">read_auth</code>{" "}
          value. Confirm the server version matches this UI.
        </p>
      ) : mismatch ? (
        <p className="fd-alert fd-alert--warn fd-security-strip__detail">
          Server expects <code className="fd-mono fd-mono--sm">Authorization: Bearer</code> for writes and reads, but{" "}
          <code className="fd-mono fd-mono--sm">VITE_FLIGHTDECK_LOCAL_API_TOKEN</code> is unset in this UI build. Set it
          to match <code className="fd-mono fd-mono--sm">FLIGHTDECK_LOCAL_API_TOKEN</code> on the server.
        </p>
      ) : mutationAuth === "bearer" && hasClient ? (
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
