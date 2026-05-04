import { useEffect, useId, useState } from "react";
import type { PricingInfo } from "./diffPayload";

export function DiffPricingExpand({
  pricing,
  resetDetailKey,
}: {
  pricing: PricingInfo;
  /** Bump when a new diff payload arrives so the fold resets closed. */
  resetDetailKey: number;
}) {
  const pricingPanelId = useId();
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    setDetailOpen(false);
  }, [resetDetailKey]);

  return (
    <div className="fd-diff-section fd-diff-section--collapse-wrap" role="region" aria-labelledby="diff-pricing-toggle">
      <div className="fd-diff-pricing-inline">
        <h4 className="fd-diff-section__title fd-m-0" id="diff-pricing-toggle">
          Pricing &amp; model
        </h4>
        <p className="fd-muted fd-type-desc fd-m-0 fd-diff-pricing-inline__summary">
          <code className="fd-mono fd-mono--sm">
            {pricing.baselineProvider}/{pricing.baselineVersion} {pricing.baselineModel}
          </code>
          <span className="fd-metric__arrow fd-mx-xs" aria-hidden>
            →
          </span>
          <code className="fd-mono fd-mono--sm">
            {pricing.candidateProvider}/{pricing.candidateVersion} {pricing.candidateModel}
          </code>
          {pricing.changed ? (
            <span className="fd-badge fd-badge--warn fd-ml-sm">pricing/model changed</span>
          ) : (
            <span className="fd-badge fd-badge--neutral fd-ml-sm">unchanged</span>
          )}
        </p>
        <button
          type="button"
          className="fd-btn fd-btn--ghost fd-diff-detail-toggle"
          data-testid="diff-pricing-expand"
          aria-expanded={detailOpen}
          aria-controls={pricingPanelId}
          onClick={() => setDetailOpen((o) => !o)}
        >
          {detailOpen ? "Hide" : "Show"} catalog, tables &amp; warnings
        </button>
      </div>
      {detailOpen ? (
        <div id={pricingPanelId} className="fd-diff-section__body fd-mt-md">
          {(() => {
            const bp = pricing.baselineProvider.trim();
            const cp = pricing.candidateProvider.trim();
            const bv = pricing.baselineVersion.trim();
            const cv = pricing.candidateVersion.trim();
            const providerSkew = bp.length > 0 && cp.length > 0 && bp !== cp;
            const versionSkew = bv.length > 0 && cv.length > 0 && bv !== cv;
            if (!providerSkew && !versionSkew) return null;
            return (
              <p className="fd-alert fd-alert--warn fd-block-mb-065" role="status">
                {versionSkew ? (
                  <>
                    Imported <strong>pricing table versions</strong> differ (
                    <code className="fd-mono fd-mono--sm">{bv}</code> vs{" "}
                    <code className="fd-mono fd-mono--sm">{cv}</code>).{" "}
                  </>
                ) : null}
                {providerSkew ? (
                  <>
                    <strong>Providers</strong> differ (
                    <code className="fd-mono fd-mono--sm">{bp}</code> vs{" "}
                    <code className="fd-mono fd-mono--sm">{cp}</code>).{" "}
                  </>
                ) : null}
                Treat per-1k and catalog lines below as resolved per release; skew can change comparability.
              </p>
            );
          })()}
          {pricing.warnings.length > 0 ? (
            <>
              <p className="fd-diff-section__title fd-mb-035">Pricing warnings</p>
              <ul className="fd-alert fd-alert--warn fd-reasons fd-mt-0">
                {pricing.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </>
          ) : null}
          {pricing.hints.length > 0 ? (
            <>
              <p className="fd-diff-section__title fd-block-mt-065-mb-035">Hints</p>
              <ul className="fd-alert fd-alert--info fd-reasons fd-mt-0">
                {pricing.hints.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            </>
          ) : null}
          {pricing.catalog && (pricing.catalog.enabled || pricing.catalog.warnings.length > 0) ? (
            <>
              <p className="fd-diff-section__title fd-block-mt-065-mb-035">Pricing catalog</p>
              <div className="fd-alert fd-alert--info fd-mt-0">
                {pricing.catalog.enabled ? (
                  <p className="fd-m-0 fd-mb-035">
                    Catalog v{pricing.catalog.version ?? "—"} · slots{" "}
                    <code className="fd-mono fd-mono--sm">{pricing.catalog.baselineSlot ?? "—"}</code> →{" "}
                    <code className="fd-mono fd-mono--sm">{pricing.catalog.candidateSlot ?? "—"}</code>
                    {pricing.catalog.baselineCost !== null &&
                    pricing.catalog.candidateCost !== null &&
                    pricing.catalog.deltaCost !== null ? (
                      <>
                        <br />
                        Comparable cost/run: {pricing.catalog.baselineCost.toFixed(6)} →{" "}
                        {pricing.catalog.candidateCost.toFixed(6)} (Δ{" "}
                        {pricing.catalog.deltaCost >= 0 ? "+" : ""}
                        {pricing.catalog.deltaCost.toFixed(6)})
                      </>
                    ) : null}
                  </p>
                ) : (
                  <p className="fd-muted fd-m-0">Catalog disabled or incomplete for this diff.</p>
                )}
                {pricing.catalog.warnings.length > 0 ? (
                  <ul className="fd-reasons fd-mb-0">
                    {pricing.catalog.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </>
          ) : null}
          {pricing.changed &&
          pricing.prices &&
          pricing.prices.baselineInput !== null &&
          pricing.prices.candidateInput !== null &&
          pricing.prices.baselineOutput !== null &&
          pricing.prices.candidateOutput !== null ? (
            <>
              <p
                className="fd-diff-section__title fd-block-mt-065-mb-035"
                data-testid="diff-per-1k-prices-title"
              >
                Per-1k token prices (USD)
              </p>
              <dl className="fd-dl fd-dl--inline fd-m-0">
                <div>
                  <dt>Input / 1k</dt>
                  <dd className="fd-mono fd-mono--sm">
                    {pricing.prices.baselineInput.toFixed(6)} → {pricing.prices.candidateInput.toFixed(6)}
                  </dd>
                </div>
                <div>
                  <dt>Output / 1k</dt>
                  <dd className="fd-mono fd-mono--sm">
                    {pricing.prices.baselineOutput.toFixed(6)} → {pricing.prices.candidateOutput.toFixed(6)}
                  </dd>
                </div>
              </dl>
              <p className="fd-muted-xs fd-mt-md">
                Cost rollups reflect pricing table and model identity; compare with catalog lines above when configured.
              </p>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
