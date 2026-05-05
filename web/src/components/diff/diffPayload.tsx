export type DiffJson = Record<string, unknown>;

export function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

export type PolicyView = {
  passed: boolean;
  reasons: string[];
  evaluatedAt: string | null;
};

export function pickPolicy(data: DiffJson): PolicyView | null {
  const p = data.policy;
  if (!isRecord(p)) return null;
  const passed = p.passed;
  const reasons = p.reasons;
  const ev = p.evaluated_at;
  return {
    passed: passed === true,
    reasons: Array.isArray(reasons) ? reasons.filter((x): x is string => typeof x === "string") : [],
    evaluatedAt: typeof ev === "string" ? ev : null,
  };
}

export type CatalogInfo = {
  enabled: boolean;
  version: string | null;
  baselineSlot: string | null;
  candidateSlot: string | null;
  baselineCost: number | null;
  candidateCost: number | null;
  deltaCost: number | null;
  warnings: string[];
};

export type PricingInfo = {
  baselineProvider: string;
  baselineVersion: string;
  baselineModel: string;
  candidateProvider: string;
  candidateVersion: string;
  candidateModel: string;
  changed: boolean;
  prices: PricingPrices | null;
  warnings: string[];
  hints: string[];
  catalog: CatalogInfo | null;
};

export type PricingPrices = {
  baselineInput: number | null;
  baselineOutput: number | null;
  candidateInput: number | null;
  candidateOutput: number | null;
};

function pickPrices(p: Record<string, unknown>): PricingPrices | null {
  const block = p.prices;
  if (!isRecord(block)) return null;
  const numOrNull = (k: string): number | null =>
    typeof block[k] === "number" && Number.isFinite(block[k]) ? (block[k] as number) : null;
  return {
    baselineInput: numOrNull("baseline_input_usd_per_1k_tokens"),
    baselineOutput: numOrNull("baseline_output_usd_per_1k_tokens"),
    candidateInput: numOrNull("candidate_input_usd_per_1k_tokens"),
    candidateOutput: numOrNull("candidate_output_usd_per_1k_tokens"),
  };
}

function pickCatalog(block: Record<string, unknown>): CatalogInfo {
  const rawW = block.warnings;
  const warnings = Array.isArray(rawW) ? rawW.filter((x): x is string => typeof x === "string") : [];
  const numOrNull = (k: string): number | null =>
    typeof block[k] === "number" && Number.isFinite(block[k]) ? (block[k] as number) : null;
  const strOrNull = (k: string): string | null =>
    typeof block[k] === "string" ? (block[k] as string) : null;
  return {
    enabled: block.enabled === true,
    version: strOrNull("catalog_version"),
    baselineSlot: strOrNull("baseline_slot_id"),
    candidateSlot: strOrNull("candidate_slot_id"),
    baselineCost: numOrNull("baseline_cost_per_run_usd"),
    candidateCost: numOrNull("candidate_cost_per_run_usd"),
    deltaCost: numOrNull("delta_cost_per_run_usd"),
    warnings,
  };
}

export function pickPricing(data: DiffJson): PricingInfo | null {
  const p = data.pricing;
  if (!isRecord(p)) return null;
  const get = (k: string): string => (typeof p[k] === "string" ? (p[k] as string) : "");
  const rawWarnings = p.warnings;
  const warnings = Array.isArray(rawWarnings)
    ? rawWarnings.filter((x): x is string => typeof x === "string")
    : [];
  const rawHints = p.hints;
  const hints = Array.isArray(rawHints) ? rawHints.filter((x): x is string => typeof x === "string") : [];
  const catRaw = p.catalog;
  const catalog = isRecord(catRaw) ? pickCatalog(catRaw) : null;
  return {
    baselineProvider: get("baseline_provider"),
    baselineVersion: get("baseline_version"),
    baselineModel: get("baseline_model"),
    candidateProvider: get("candidate_provider"),
    candidateVersion: get("candidate_version"),
    candidateModel: get("candidate_model"),
    changed: p.pricing_or_model_changed === true,
    prices: pickPrices(p),
    warnings,
    hints,
    catalog,
  };
}

export function pricingLine(pricing: PricingInfo | null, side: "baseline" | "candidate"): string {
  if (!pricing) return "—";
  const prov = side === "baseline" ? pricing.baselineProvider : pricing.candidateProvider;
  const ver = side === "baseline" ? pricing.baselineVersion : pricing.candidateVersion;
  const mod = side === "baseline" ? pricing.baselineModel : pricing.candidateModel;
  const parts = [prov.trim(), ver.trim(), mod.trim()].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "—";
}

export function DiffMetric({
  label,
  baseline,
  candidate,
  delta,
  suffix = "",
}: {
  label: string;
  baseline: string;
  candidate: string;
  delta?: string;
  suffix?: string;
}) {
  return (
    <div className="fd-metric">
      <div className="fd-metric__label">{label}</div>
      <div className="fd-metric__row">
        <span className="fd-metric__bc">
          <span className="fd-metric__tag">B</span> {baseline}
          {suffix}
        </span>
        <span className="fd-metric__arrow" aria-hidden>
          →
        </span>
        <span className="fd-metric__bc">
          <span className="fd-metric__tag">C</span> {candidate}
          {suffix}
        </span>
      </div>
      {delta ? <div className="fd-metric__delta">{delta}</div> : null}
    </div>
  );
}
