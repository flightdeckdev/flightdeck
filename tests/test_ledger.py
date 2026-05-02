from __future__ import annotations

from datetime import datetime, timezone

import pytest

from flightdeck.ledger import diff_releases
from flightdeck.models import (
    Policy,
    PricingEntry,
    PricingTable,
    RunEvent,
    RunEventMetrics,
    RunEventModelUsage,
    RunEventUsage,
    WorkspaceConfig,
)


def _event(
    *,
    agent_id: str,
    run_id: str,
    release_id: str,
    latency_ms: int | None = 100,
    success: bool = True,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> RunEvent:
    return RunEvent(
        timestamp=datetime.now(tz=timezone.utc),
        agent_id=agent_id,
        release_id=release_id,
        run_id=run_id,
        tenant_id="t",
        task_id="task",
        environment="local",
        usage=RunEventUsage(
            model=RunEventModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        ),
        metrics=RunEventMetrics(latency_ms=latency_ms, success=success),
    )


def _pricing_table() -> PricingTable:
    return PricingTable(
        provider="openai",
        pricing_version="p",
        entries=[
            PricingEntry(
                model="gpt-4.1-mini",
                input_usd_per_1k_tokens=1.0,
                output_usd_per_1k_tokens=2.0,
            )
        ],
    )


def test_diff_releases_rejects_cross_agent_run_events() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(require_high_diff_confidence=False)
    b = _event(agent_id="agent_a", run_id="r1", release_id="rel_b")
    c = _event(agent_id="agent_b", run_id="r2", release_id="rel_c")
    table = _pricing_table()

    with pytest.raises(ValueError, match="Cross-agent diff rejected"):
        diff_releases(
            cfg=cfg,
            policy=policy,
            baseline_events=[b],
            candidate_events=[c],
            baseline_pricing_table=table,
            candidate_pricing_table=table,
            window="7d",
        )


def test_diff_releases_rejects_mixed_agents_within_side() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(require_high_diff_confidence=False)
    b1 = _event(agent_id="agent_a", run_id="r1", release_id="rel_b")
    b2 = _event(agent_id="agent_x", run_id="r2", release_id="rel_b")
    c1 = _event(agent_id="agent_a", run_id="r3", release_id="rel_c")
    table = _pricing_table()

    with pytest.raises(ValueError, match="single consistent agent_id"):
        diff_releases(
            cfg=cfg,
            policy=policy,
            baseline_events=[b1, b2],
            candidate_events=[c1],
            baseline_pricing_table=table,
            candidate_pricing_table=table,
            window="7d",
        )


def test_diff_releases_respects_zero_policy_sample_thresholds() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(
        min_baseline_runs=0,
        min_candidate_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=True,
    )
    table = _pricing_table()

    result = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=[],
        candidate_events=[],
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )

    assert result.confidence == "HIGH"
    assert result.policy.passed


def _events(*, n: int, release_id: str, agent_id: str = "agent_a", **kwargs) -> list[RunEvent]:
    return [_event(agent_id=agent_id, run_id=f"{release_id}_{i}", release_id=release_id, **kwargs) for i in range(n)]


def test_medium_confidence_blocks_when_require_high_flag_set() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(require_high_diff_confidence=True)
    table = _pricing_table()

    result = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=200, release_id="rel_b"),
        candidate_events=_events(n=200, release_id="rel_c"),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )

    assert result.confidence == "MEDIUM"
    assert not result.policy.passed
    assert any("MEDIUM" in r for r in result.policy.reasons)
    assert any("HIGH" in r for r in result.policy.reasons)


def test_medium_confidence_passes_without_require_high_flag() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(require_high_diff_confidence=False)
    table = _pricing_table()

    result = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=200, release_id="rel_b"),
        candidate_events=_events(n=200, release_id="rel_c"),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )

    assert result.confidence == "MEDIUM"
    assert result.policy.passed


def test_confidence_reason_populated_for_medium_and_low() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(require_high_diff_confidence=False)
    table = _pricing_table()

    medium = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=200, release_id="rel_b"),
        candidate_events=_events(n=200, release_id="rel_c"),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )
    assert medium.confidence == "MEDIUM"
    assert medium.confidence_reason
    assert "sample" in medium.confidence_reason

    low = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=10, release_id="rel_b"),
        candidate_events=_events(n=200, release_id="rel_c"),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )
    assert low.confidence == "LOW"
    assert low.confidence_reason
    assert "sample" in low.confidence_reason or "floor" in low.confidence_reason


def test_low_floor_boundary() -> None:
    cfg = WorkspaceConfig()
    # Override defaults so we can drive the LOW floor at runs=50 deterministically.
    policy = Policy(
        min_baseline_runs=500,
        min_candidate_runs=500,
        min_low_runs=50,
        require_high_diff_confidence=False,
    )
    table = _pricing_table()

    just_below = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=49, release_id="rel_b"),
        candidate_events=_events(n=200, release_id="rel_c"),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )
    assert just_below.confidence == "LOW"

    at_floor = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=50, release_id="rel_b"),
        candidate_events=_events(n=200, release_id="rel_c"),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )
    assert at_floor.confidence == "MEDIUM"


def test_policy_max_latency_ms_blocks() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(
        max_latency_ms=50,
        min_baseline_runs=0,
        min_candidate_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=False,
    )
    table = _pricing_table()

    result = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=5, release_id="rel_b", latency_ms=100),
        candidate_events=_events(n=5, release_id="rel_c", latency_ms=200),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )

    assert not result.policy.passed
    assert any("latency_ms_avg" in r for r in result.policy.reasons)


def test_policy_max_latency_ms_skipped_when_no_data() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(
        max_latency_ms=50,
        min_baseline_runs=0,
        min_candidate_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=False,
    )
    table = _pricing_table()

    result = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=5, release_id="rel_b", latency_ms=None),
        candidate_events=_events(n=5, release_id="rel_c", latency_ms=None),
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )

    assert result.candidate.latency_ms_avg is None
    assert result.policy.passed
    assert not any("latency" in r for r in result.policy.reasons)


def test_policy_max_error_rate_blocks() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(
        max_error_rate=0.1,
        min_baseline_runs=0,
        min_candidate_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=False,
    )
    table = _pricing_table()

    candidate_events = [
        _event(agent_id="agent_a", run_id=f"c_{i}", release_id="rel_c", success=(i < 4))
        for i in range(8)
    ]

    result = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=5, release_id="rel_b"),
        candidate_events=candidate_events,
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )

    assert result.candidate.error_rate == 0.5
    assert not result.policy.passed
    assert any("error_rate" in r for r in result.policy.reasons)


def test_policy_multiple_failures_accumulate() -> None:
    cfg = WorkspaceConfig()
    policy = Policy(
        max_cost_per_run_usd=0.0001,
        max_error_rate=0.1,
        min_baseline_runs=0,
        min_candidate_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=False,
    )
    table = _pricing_table()

    candidate_events = [
        _event(agent_id="agent_a", run_id=f"c_{i}", release_id="rel_c", success=(i < 4))
        for i in range(8)
    ]

    result = diff_releases(
        cfg=cfg,
        policy=policy,
        baseline_events=_events(n=5, release_id="rel_b"),
        candidate_events=candidate_events,
        baseline_pricing_table=table,
        candidate_pricing_table=table,
        window="7d",
    )

    assert not result.policy.passed
    assert any("cost_per_run_usd" in r for r in result.policy.reasons)
    assert any("error_rate" in r for r in result.policy.reasons)
    assert len(result.policy.reasons) >= 2
