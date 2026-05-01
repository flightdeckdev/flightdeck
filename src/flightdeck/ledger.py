from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from flightdeck.models import Policy, PolicyResult, PricingEntry, PricingTable, RunEvent, WorkspaceConfig


def parse_window(window: str) -> timedelta:
    """
    Parse a simple window string like '7d', '24h', '30m'.
    """
    window = window.strip().lower()
    if len(window) < 2:
        raise ValueError(f"Invalid window: {window}")

    unit = window[-1]
    try:
        value = int(window[:-1])
    except ValueError as e:
        raise ValueError(f"Invalid window: {window}") from e
    if value <= 0:
        raise ValueError(f"Invalid window: {window}")

    if unit == "d":
        return timedelta(days=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "m":
        return timedelta(minutes=value)

    raise ValueError(f"Invalid window unit: {window}")


def confidence_label(
    baseline_runs: int,
    candidate_runs: int,
    *,
    min_baseline_runs: int,
    min_candidate_runs: int,
    min_low_runs: int,
) -> Literal["HIGH", "MEDIUM", "LOW"]:
    if baseline_runs >= min_baseline_runs and candidate_runs >= min_candidate_runs:
        return "HIGH"
    if baseline_runs < min_low_runs or candidate_runs < min_low_runs:
        return "LOW"
    return "MEDIUM"


def pricing_entry_for(table: PricingTable, model: str) -> PricingEntry | None:
    for e in table.entries:
        if e.model == model:
            return e
    return None


def estimate_cost_usd(event: RunEvent, pricing_table: PricingTable) -> float:
    entry = pricing_entry_for(pricing_table, event.usage.model.model)
    if entry is None:
        raise KeyError(f"Pricing missing for model: {event.usage.model.model}")

    in_cost = (event.usage.model.input_tokens / 1000.0) * entry.input_usd_per_1k_tokens
    out_cost = (event.usage.model.output_tokens / 1000.0) * entry.output_usd_per_1k_tokens
    cached = 0.0
    if entry.cached_input_usd_per_1k_tokens is not None:
        cached = (event.usage.model.cached_input_tokens / 1000.0) * entry.cached_input_usd_per_1k_tokens
    return in_cost + out_cost + cached


@dataclass(frozen=True)
class Rollup:
    runs: int
    cost_per_run_usd: float
    latency_ms_avg: float | None
    error_rate: float


def compute_rollup(events: list[RunEvent], pricing_table: PricingTable) -> Rollup:
    if not events:
        return Rollup(runs=0, cost_per_run_usd=0.0, latency_ms_avg=None, error_rate=0.0)

    total_cost = 0.0
    total_latency = 0.0
    latency_count = 0
    error_count = 0

    for e in events:
        total_cost += estimate_cost_usd(e, pricing_table)
        if e.metrics.latency_ms is not None:
            total_latency += e.metrics.latency_ms
            latency_count += 1
        if not e.metrics.success:
            error_count += 1

    return Rollup(
        runs=len(events),
        cost_per_run_usd=(total_cost / len(events)),
        latency_ms_avg=(total_latency / latency_count) if latency_count else None,
        error_rate=(error_count / len(events)),
    )


@dataclass(frozen=True)
class DiffResult:
    baseline_runs: int
    candidate_runs: int
    window: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    confidence_reason: str | None

    baseline: Rollup
    candidate: Rollup

    delta_cost_per_run_usd: float
    delta_cost_per_run_pct: float | None
    delta_latency_ms_avg: float | None
    delta_error_rate: float

    policy: PolicyResult


def evaluate_policy(
    policy: Policy,
    *,
    candidate: Rollup,
    baseline: Rollup,
    diff_confidence: Literal["HIGH", "MEDIUM", "LOW"],
    diff_confidence_reason: str | None,
) -> PolicyResult:
    reasons: list[str] = []

    # Cost
    if policy.max_cost_per_run_usd is not None and candidate.cost_per_run_usd > policy.max_cost_per_run_usd:
        reasons.append(
            f"candidate cost_per_run_usd {candidate.cost_per_run_usd:.6f} exceeds max {policy.max_cost_per_run_usd:.6f}"
        )

    # Latency
    if policy.max_latency_ms is not None and candidate.latency_ms_avg is not None:
        if candidate.latency_ms_avg > policy.max_latency_ms:
            reasons.append(
                f"candidate latency_ms_avg {candidate.latency_ms_avg:.2f} exceeds max {policy.max_latency_ms}"
            )

    # Error rate
    if policy.max_error_rate is not None:
        if candidate.error_rate > policy.max_error_rate:
            reasons.append(
                f"candidate error_rate {candidate.error_rate:.4f} exceeds max {policy.max_error_rate:.4f}"
            )

    if policy.require_high_diff_confidence and diff_confidence != "HIGH":
        suffix = f" ({diff_confidence_reason})" if diff_confidence_reason else ""
        reasons.append(f"diff confidence is {diff_confidence}{suffix}; promotion requires HIGH")

    return PolicyResult(passed=(len(reasons) == 0), reasons=reasons)


def diff_releases(
    *,
    cfg: WorkspaceConfig,
    policy: Policy,
    baseline_events: list[RunEvent],
    candidate_events: list[RunEvent],
    baseline_pricing_table: PricingTable,
    candidate_pricing_table: PricingTable,
    window: str,
) -> DiffResult:
    if baseline_events and candidate_events:
        b_agents = {e.agent_id for e in baseline_events}
        c_agents = {e.agent_id for e in candidate_events}
        if len(b_agents) != 1 or len(c_agents) != 1:
            raise ValueError(
                "Each side of the diff must have a single consistent agent_id among run events."
            )
        if next(iter(b_agents)) != next(iter(c_agents)):
            raise ValueError(
                "Cross-agent diff rejected: baseline and candidate run events must share the same agent_id."
            )

    baseline_rollup = compute_rollup(baseline_events, baseline_pricing_table)
    candidate_rollup = compute_rollup(candidate_events, candidate_pricing_table)

    # Confidence (policy can override thresholds; otherwise take config defaults)
    min_candidate_runs = (
        policy.min_candidate_runs if policy.min_candidate_runs is not None else cfg.diff.min_candidate_runs
    )
    min_baseline_runs = policy.min_baseline_runs if policy.min_baseline_runs is not None else cfg.diff.min_baseline_runs
    min_low_runs = policy.min_low_runs if policy.min_low_runs is not None else cfg.diff.min_low_runs

    label = confidence_label(
        baseline_rollup.runs,
        candidate_rollup.runs,
        min_candidate_runs=min_candidate_runs,
        min_baseline_runs=min_baseline_runs,
        min_low_runs=min_low_runs,
    )
    reason = None
    if label != "HIGH":
        parts: list[str] = []
        if candidate_rollup.runs < min_candidate_runs:
            parts.append(f"candidate sample < {min_candidate_runs} runs")
        if baseline_rollup.runs < min_baseline_runs:
            parts.append(f"baseline sample < {min_baseline_runs} runs")
        if candidate_rollup.runs < min_low_runs or baseline_rollup.runs < min_low_runs:
            parts.append(f"LOW floor is {min_low_runs} runs")
        reason = "; ".join(parts) if parts else "insufficient sample size"

    # Deltas
    delta_cost = candidate_rollup.cost_per_run_usd - baseline_rollup.cost_per_run_usd
    delta_cost_pct = None
    if baseline_rollup.cost_per_run_usd > 0:
        delta_cost_pct = delta_cost / baseline_rollup.cost_per_run_usd

    delta_latency = None
    if baseline_rollup.latency_ms_avg is not None and candidate_rollup.latency_ms_avg is not None:
        delta_latency = candidate_rollup.latency_ms_avg - baseline_rollup.latency_ms_avg

    delta_error_rate = candidate_rollup.error_rate - baseline_rollup.error_rate

    policy_result = evaluate_policy(
        policy,
        candidate=candidate_rollup,
        baseline=baseline_rollup,
        diff_confidence=label,
        diff_confidence_reason=reason,
    )

    return DiffResult(
        baseline_runs=baseline_rollup.runs,
        candidate_runs=candidate_rollup.runs,
        window=window,
        confidence=label,
        confidence_reason=reason,
        baseline=baseline_rollup,
        candidate=candidate_rollup,
        delta_cost_per_run_usd=delta_cost,
        delta_cost_per_run_pct=delta_cost_pct,
        delta_latency_ms_avg=delta_latency,
        delta_error_rate=delta_error_rate,
        policy=policy_result,
    )

