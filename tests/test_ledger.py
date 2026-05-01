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


def _event(*, agent_id: str, run_id: str, release_id: str) -> RunEvent:
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
                input_tokens=100,
                output_tokens=50,
            )
        ),
        metrics=RunEventMetrics(latency_ms=100, success=True),
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
