from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import uuid4

from flightdeck.ledger import diff_releases, parse_window, pricing_entry_for
from flightdeck.models import (
    Policy,
    PolicyResult,
    PromotionRecord,
    ReleaseArtifact,
    ReleaseRecord,
    WorkspaceConfig,
    utc_now,
)
from flightdeck.storage import Storage


class OperationError(ValueError):
    """User-facing operation error that callers can map to CLI/HTTP surfaces."""


@dataclass(frozen=True)
class DiffOutcome:
    window: str
    since: datetime
    until: datetime
    environment: str
    tenant_id: str | None
    task_id: str | None
    baseline_pricing_provider: str
    baseline_pricing_version: str
    baseline_model: str
    baseline_input_usd_per_1k_tokens: float | None
    baseline_output_usd_per_1k_tokens: float | None
    baseline_cached_input_usd_per_1k_tokens: float | None
    candidate_pricing_provider: str
    candidate_pricing_version: str
    candidate_model: str
    candidate_input_usd_per_1k_tokens: float | None
    candidate_output_usd_per_1k_tokens: float | None
    candidate_cached_input_usd_per_1k_tokens: float | None
    pricing_or_model_changed: bool
    baseline_runs: int
    candidate_runs: int
    confidence: str
    confidence_reason: str | None
    baseline_cost_per_run_usd: float
    candidate_cost_per_run_usd: float
    delta_cost_per_run_usd: float
    delta_cost_per_run_pct: float | None
    baseline_latency_ms_avg: float | None
    candidate_latency_ms_avg: float | None
    delta_latency_ms_avg: float | None
    baseline_error_rate: float
    candidate_error_rate: float
    delta_error_rate: float
    policy: PolicyResult
    pricing_warnings: tuple[str, ...]


@dataclass(frozen=True)
class ActionOutcome:
    action_id: str
    action: str
    release_id: str
    agent_id: str
    environment: str
    baseline_release_id: str | None
    promoted_pointer_changed: bool
    policy: PolicyResult


@dataclass(frozen=True)
class TimelineOutcome:
    releases: list[dict[str, object]]
    promoted: list[dict[str, str]]
    actions: list[dict[str, object]]


def default_policy() -> Policy:
    return Policy(
        max_cost_per_run_usd=None,
        max_latency_ms=None,
        max_error_rate=None,
    )


def _load_release_or_error(storage: Storage, release_id: str, *, role: str) -> tuple[ReleaseRecord, ReleaseArtifact]:
    record = storage.get_release(release_id)
    if not record:
        if role == "baseline":
            raise OperationError(f"Unknown baseline release: {release_id}")
        if role == "candidate":
            raise OperationError(f"Unknown candidate release: {release_id}")
        raise OperationError(f"Unknown release: {release_id}")
    return record, ReleaseArtifact.model_validate(record.artifact_json)


def _load_pricing_or_error(storage: Storage, *, provider: str, version: str, role: str):
    table = storage.get_pricing_table(provider, version)
    if table:
        return table
    if role == "baseline":
        raise OperationError(f"Missing pricing table for baseline {provider}/{version}. Run `flightdeck pricing import ...`.")
    if role == "candidate":
        raise OperationError(
            f"Missing pricing table for candidate {provider}/{version}. Run `flightdeck pricing import ...`."
        )
    if role == "rollback":
        raise OperationError(
            f"Missing pricing table for rollback target {provider}/{version}. Run `flightdeck pricing import ...`."
        )
    raise OperationError(
        f"Missing pricing table for promoted baseline {provider}/{version}. Run `flightdeck pricing import ...`."
    )


def compute_diff(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    baseline_release_id: str,
    candidate_release_id: str,
    window: str,
    environment: str | None,
    tenant_id: str | None,
    task_id: str | None,
) -> DiffOutcome:
    _, base_artifact = _load_release_or_error(storage, baseline_release_id, role="baseline")
    _, cand_artifact = _load_release_or_error(storage, candidate_release_id, role="candidate")

    if base_artifact.spec.agent.agent_id != cand_artifact.spec.agent.agent_id:
        raise OperationError(
            "Cross-agent diff is not allowed. "
            f"Baseline agent_id={base_artifact.spec.agent.agent_id}, "
            f"candidate agent_id={cand_artifact.spec.agent.agent_id}."
        )

    env = environment or cfg.default_environment
    base_ref = base_artifact.spec.pricing_reference
    cand_ref = cand_artifact.spec.pricing_reference
    base_table = _load_pricing_or_error(storage, provider=base_ref.provider, version=base_ref.pricing_version, role="baseline")
    cand_table = _load_pricing_or_error(storage, provider=cand_ref.provider, version=cand_ref.pricing_version, role="candidate")

    try:
        delta = parse_window(window)
    except ValueError as e:
        raise OperationError(str(e)) from e

    until = utc_now()
    since = until - delta
    baseline_events = storage.query_runs(
        baseline_release_id,
        since,
        until,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=env,
    )
    candidate_events = storage.query_runs(
        candidate_release_id,
        since,
        until,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=env,
    )

    policy = storage.get_active_policy() or default_policy()
    try:
        diff = diff_releases(
            cfg=cfg,
            policy=policy,
            baseline_events=baseline_events,
            candidate_events=candidate_events,
            baseline_pricing_table=base_table,
            candidate_pricing_table=cand_table,
            window=window,
        )
    except KeyError as e:
        raise OperationError(
            "Pricing table missing model entry. "
            f"baseline_model={base_artifact.spec.runtime.model} "
            f"candidate_model={cand_artifact.spec.runtime.model}. "
            f"Check pricing tables: {base_ref.provider}/{base_ref.pricing_version} and "
            f"{cand_ref.provider}/{cand_ref.pricing_version}."
        ) from e
    except ValueError as e:
        raise OperationError(str(e)) from e

    base_entry = pricing_entry_for(base_table, base_artifact.spec.runtime.model)
    cand_entry = pricing_entry_for(cand_table, cand_artifact.spec.runtime.model)

    pricing_warnings: list[str] = []
    if base_entry is None:
        pricing_warnings.append(
            f"baseline pricing table {base_ref.provider}/{base_ref.pricing_version} "
            f"has no entry for model {base_artifact.spec.runtime.model!r}"
        )
    if cand_entry is None:
        pricing_warnings.append(
            f"candidate pricing table {cand_ref.provider}/{cand_ref.pricing_version} "
            f"has no entry for model {cand_artifact.spec.runtime.model!r}"
        )

    return DiffOutcome(
        window=window,
        since=since,
        until=until,
        environment=env,
        tenant_id=tenant_id,
        task_id=task_id,
        baseline_pricing_provider=base_ref.provider,
        baseline_pricing_version=base_ref.pricing_version,
        baseline_model=base_artifact.spec.runtime.model,
        baseline_input_usd_per_1k_tokens=base_entry.input_usd_per_1k_tokens if base_entry else None,
        baseline_output_usd_per_1k_tokens=base_entry.output_usd_per_1k_tokens if base_entry else None,
        baseline_cached_input_usd_per_1k_tokens=(
            base_entry.cached_input_usd_per_1k_tokens if base_entry else None
        ),
        candidate_pricing_provider=cand_ref.provider,
        candidate_pricing_version=cand_ref.pricing_version,
        candidate_model=cand_artifact.spec.runtime.model,
        candidate_input_usd_per_1k_tokens=cand_entry.input_usd_per_1k_tokens if cand_entry else None,
        candidate_output_usd_per_1k_tokens=cand_entry.output_usd_per_1k_tokens if cand_entry else None,
        candidate_cached_input_usd_per_1k_tokens=(
            cand_entry.cached_input_usd_per_1k_tokens if cand_entry else None
        ),
        pricing_or_model_changed=(
            base_ref.provider != cand_ref.provider
            or base_ref.pricing_version != cand_ref.pricing_version
            or base_artifact.spec.runtime.model != cand_artifact.spec.runtime.model
        ),
        baseline_runs=diff.baseline_runs,
        candidate_runs=diff.candidate_runs,
        confidence=diff.confidence,
        confidence_reason=diff.confidence_reason,
        baseline_cost_per_run_usd=diff.baseline.cost_per_run_usd,
        candidate_cost_per_run_usd=diff.candidate.cost_per_run_usd,
        delta_cost_per_run_usd=diff.delta_cost_per_run_usd,
        delta_cost_per_run_pct=diff.delta_cost_per_run_pct,
        baseline_latency_ms_avg=diff.baseline.latency_ms_avg,
        candidate_latency_ms_avg=diff.candidate.latency_ms_avg,
        delta_latency_ms_avg=diff.delta_latency_ms_avg,
        baseline_error_rate=diff.baseline.error_rate,
        candidate_error_rate=diff.candidate.error_rate,
        delta_error_rate=diff.delta_error_rate,
        policy=diff.policy,
        pricing_warnings=tuple(pricing_warnings),
    )


def _evaluate_promotion_or_rollback(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    action: Literal["promote", "rollback"],
    release_id: str,
    environment: str,
    window: str,
    reason: str,
    actor: str,
) -> ActionOutcome:
    if not reason.strip():
        raise OperationError("Reason is required for promote/rollback actions.")

    _, target_artifact = _load_release_or_error(storage, release_id, role="target")
    agent_id = target_artifact.spec.agent.agent_id
    current_release_id = storage.get_promoted_release_id(agent_id, environment)
    active_policy = storage.get_active_policy() or default_policy()

    if action == "promote" and not current_release_id:
        policy_result = PolicyResult(
            passed=True,
            reasons=["first promotion: no promoted baseline for agent/environment"],
        )
    else:
        if not current_release_id:
            raise OperationError("No promoted release exists for this agent/environment; nothing to roll back to.")
        baseline_record = storage.get_release(current_release_id)
        if not baseline_record:
            raise OperationError(f"Promoted baseline release is missing: {current_release_id}")

        baseline_artifact = ReleaseArtifact.model_validate(baseline_record.artifact_json)
        baseline_ref = baseline_artifact.spec.pricing_reference
        candidate_ref = target_artifact.spec.pricing_reference
        baseline_table = _load_pricing_or_error(
            storage,
            provider=baseline_ref.provider,
            version=baseline_ref.pricing_version,
            role="promoted_baseline",
        )
        candidate_table = _load_pricing_or_error(
            storage,
            provider=candidate_ref.provider,
            version=candidate_ref.pricing_version,
            role="candidate" if action == "promote" else "rollback",
        )

        try:
            delta = parse_window(window)
        except ValueError as e:
            raise OperationError(str(e)) from e
        until = utc_now()
        since = until - delta

        baseline_events = storage.query_runs(
            current_release_id,
            since,
            until,
            environment=environment,
        )
        candidate_events = storage.query_runs(
            release_id,
            since,
            until,
            environment=environment,
        )

        try:
            diff = diff_releases(
                cfg=cfg,
                policy=active_policy,
                baseline_events=baseline_events,
                candidate_events=candidate_events,
                baseline_pricing_table=baseline_table,
                candidate_pricing_table=candidate_table,
                window=window,
            )
        except KeyError as e:
            raise OperationError(
                "Pricing table missing model entry. "
                f"baseline_model={baseline_artifact.spec.runtime.model} "
                f"candidate_model={target_artifact.spec.runtime.model}."
            ) from e
        except ValueError as e:
            raise OperationError(str(e)) from e
        policy_result = diff.policy

    action_id = f"act_{uuid4().hex[:12]}"
    record = PromotionRecord(
        action_id=action_id,
        action=action,
        actor=actor,
        release_id=release_id,
        agent_id=agent_id,
        environment=environment,
        reason=reason,
        policy_result=policy_result,
        baseline_release_id=current_release_id,
        created_at=utc_now(),
    )

    if not policy_result.passed:
        storage.insert_promotion_record(record)
        return ActionOutcome(
            action_id=action_id,
            action=action,
            release_id=release_id,
            agent_id=agent_id,
            environment=environment,
            baseline_release_id=current_release_id,
            promoted_pointer_changed=False,
            policy=policy_result,
        )

    storage.commit_promotion(record, new_promoted_release_id=release_id)
    return ActionOutcome(
        action_id=action_id,
        action=action,
        release_id=release_id,
        agent_id=agent_id,
        environment=environment,
        baseline_release_id=current_release_id,
        promoted_pointer_changed=True,
        policy=policy_result,
    )


def promote_release(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    release_id: str,
    environment: str,
    window: str,
    reason: str,
    actor: str,
) -> ActionOutcome:
    return _evaluate_promotion_or_rollback(
        cfg=cfg,
        storage=storage,
        action="promote",
        release_id=release_id,
        environment=environment,
        window=window,
        reason=reason,
        actor=actor,
    )


def rollback_release(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    release_id: str,
    environment: str,
    window: str,
    reason: str,
    actor: str,
) -> ActionOutcome:
    return _evaluate_promotion_or_rollback(
        cfg=cfg,
        storage=storage,
        action="rollback",
        release_id=release_id,
        environment=environment,
        window=window,
        reason=reason,
        actor=actor,
    )


def list_timeline(
    *,
    storage: Storage,
    agent_id: str | None = None,
    environment: str | None = None,
    action_limit: int = 50,
) -> TimelineOutcome:
    releases = [
        {
            "release_id": r.release_id,
            "agent_id": r.agent_id,
            "version": r.version,
            "environment": r.environment,
            "checksum": r.checksum,
            "created_at": r.created_at.isoformat(),
        }
        for r in storage.list_releases()
    ]
    promoted = [
        {"agent_id": a, "environment": e, "release_id": rid}
        for (a, e, rid) in storage.list_promoted_pointers()
    ]
    actions = []
    for a in storage.list_release_actions(agent_id=agent_id, environment=environment)[: max(0, action_limit)]:
        actions.append(
            {
                "action_id": a.action_id,
                "action": a.action,
                "release_id": a.release_id,
                "agent_id": a.agent_id,
                "environment": a.environment,
                "baseline_release_id": a.baseline_release_id,
                "reason": a.reason,
                "policy_passed": a.policy_result.passed,
                "policy_reasons": a.policy_result.reasons,
                "created_at": a.created_at.isoformat(),
                "audit_seq": a.audit_seq,
            }
        )
    return TimelineOutcome(releases=releases, promoted=promoted, actions=actions)
