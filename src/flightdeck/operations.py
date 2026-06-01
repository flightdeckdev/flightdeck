from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import yaml
from pydantic import ValidationError

from flightdeck.bundled_pricing_age import bundled_pricing_stale_warning
from flightdeck.catalog import (
    catalog_tariff_as_table,
    load_pricing_catalog,
    resolve_catalog_pricing_entry,
    resolve_catalog_slot_id,
)
from flightdeck.ledger import compute_rollup, diff_releases, parse_window, pricing_entry_for
from flightdeck.models import (
    Policy,
    PolicyResult,
    PromotionRecord,
    PromotionRequestRecord,
    ReleaseArtifact,
    ReleaseRecord,
    WorkspaceConfig,
    utc_now,
)
from flightdeck.pricing_hints import collect_pricing_skew_hints
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
    pricing_hints: tuple[str, ...]
    catalog_enabled: bool
    catalog_version: str | None
    baseline_catalog_slot_id: str | None
    candidate_catalog_slot_id: str | None
    baseline_catalog_cost_per_run_usd: float | None
    candidate_catalog_cost_per_run_usd: float | None
    delta_catalog_cost_per_run_usd: float | None
    catalog_warnings: tuple[str, ...]
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


def diff_outcome_to_public_dict(result: DiffOutcome) -> dict[str, object]:
    """JSON shape for ``POST /v1/diff`` and ``release diff --output json``."""
    return {
        "window": result.window,
        "since": result.since.isoformat(),
        "until": result.until.isoformat(),
        "filters": {
            "environment": result.environment,
            "tenant_id": result.tenant_id,
            "task_id": result.task_id,
        },
        "pricing": {
            "baseline_provider": result.baseline_pricing_provider,
            "baseline_version": result.baseline_pricing_version,
            "baseline_model": result.baseline_model,
            "candidate_provider": result.candidate_pricing_provider,
            "candidate_version": result.candidate_pricing_version,
            "candidate_model": result.candidate_model,
            "pricing_or_model_changed": result.pricing_or_model_changed,
            "prices": {
                "baseline_input_usd_per_1k_tokens": result.baseline_input_usd_per_1k_tokens,
                "baseline_output_usd_per_1k_tokens": result.baseline_output_usd_per_1k_tokens,
                "baseline_cached_input_usd_per_1k_tokens": result.baseline_cached_input_usd_per_1k_tokens,
                "candidate_input_usd_per_1k_tokens": result.candidate_input_usd_per_1k_tokens,
                "candidate_output_usd_per_1k_tokens": result.candidate_output_usd_per_1k_tokens,
                "candidate_cached_input_usd_per_1k_tokens": result.candidate_cached_input_usd_per_1k_tokens,
            },
            "warnings": list(result.pricing_warnings),
            "hints": list(result.pricing_hints),
            "catalog": {
                "enabled": result.catalog_enabled,
                "catalog_version": result.catalog_version,
                "baseline_slot_id": result.baseline_catalog_slot_id,
                "candidate_slot_id": result.candidate_catalog_slot_id,
                "baseline_cost_per_run_usd": result.baseline_catalog_cost_per_run_usd,
                "candidate_cost_per_run_usd": result.candidate_catalog_cost_per_run_usd,
                "delta_cost_per_run_usd": result.delta_catalog_cost_per_run_usd,
                "warnings": list(result.catalog_warnings),
            },
        },
        "samples": {
            "baseline_runs": result.baseline_runs,
            "candidate_runs": result.candidate_runs,
            "confidence": result.confidence,
            "confidence_reason": result.confidence_reason,
        },
        "metrics": {
            "baseline_cost_per_run_usd": result.baseline_cost_per_run_usd,
            "candidate_cost_per_run_usd": result.candidate_cost_per_run_usd,
            "delta_cost_per_run_usd": result.delta_cost_per_run_usd,
            "delta_cost_per_run_pct": result.delta_cost_per_run_pct,
            "baseline_latency_ms_avg": result.baseline_latency_ms_avg,
            "candidate_latency_ms_avg": result.candidate_latency_ms_avg,
            "delta_latency_ms_avg": result.delta_latency_ms_avg,
            "baseline_error_rate": result.baseline_error_rate,
            "candidate_error_rate": result.candidate_error_rate,
            "delta_error_rate": result.delta_error_rate,
        },
        "policy": result.policy.model_dump(mode="json"),
    }


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

    pricing_hints: list[str] = []
    pricing_hints.extend(
        collect_pricing_skew_hints(
            storage,
            role="baseline",
            ref=base_ref,
            model=base_artifact.spec.runtime.model,
            table=base_table,
            model_in_table=base_entry is not None,
        )
    )
    pricing_hints.extend(
        collect_pricing_skew_hints(
            storage,
            role="candidate",
            ref=cand_ref,
            model=cand_artifact.spec.runtime.model,
            table=cand_table,
            model_in_table=cand_entry is not None,
        )
    )

    _warned_versions: set[str] = set()
    for ref, role in ((base_ref, "baseline"), (cand_ref, "candidate")):
        pv = ref.pricing_version
        if pv in _warned_versions:
            continue
        _warned_versions.add(pv)
        stale = bundled_pricing_stale_warning(pv, role=role)
        if stale:
            pricing_warnings.append(stale)

    catalog_enabled = False
    catalog_version: str | None = None
    baseline_catalog_slot_id: str | None = None
    candidate_catalog_slot_id: str | None = None
    baseline_catalog_cost: float | None = None
    candidate_catalog_cost: float | None = None
    delta_catalog_cost: float | None = None
    catalog_warnings: list[str] = []

    if cfg.pricing_catalog_path:
        cat_path = Path(cfg.pricing_catalog_path)
        if not cat_path.is_absolute():
            cat_path = Path.cwd() / cat_path
        try:
            catalog = load_pricing_catalog(cat_path)
            catalog_enabled = True
            catalog_version = catalog.catalog_version
            baseline_catalog_slot_id = resolve_catalog_slot_id(
                catalog,
                provider=base_ref.provider,
                pricing_version=base_ref.pricing_version,
                model=base_artifact.spec.runtime.model,
            )
            candidate_catalog_slot_id = resolve_catalog_slot_id(
                catalog,
                provider=cand_ref.provider,
                pricing_version=cand_ref.pricing_version,
                model=cand_artifact.spec.runtime.model,
            )
            b_cat_entry, b_err = resolve_catalog_pricing_entry(
                catalog,
                provider=base_ref.provider,
                pricing_version=base_ref.pricing_version,
                model=base_artifact.spec.runtime.model,
            )
            c_cat_entry, c_err = resolve_catalog_pricing_entry(
                catalog,
                provider=cand_ref.provider,
                pricing_version=cand_ref.pricing_version,
                model=cand_artifact.spec.runtime.model,
            )
            if b_err:
                catalog_warnings.append(f"baseline: {b_err}")
            if c_err:
                catalog_warnings.append(f"candidate: {c_err}")
            if b_cat_entry is not None and c_cat_entry is not None:
                b_tab = catalog_tariff_as_table(base_artifact.spec.runtime.model, b_cat_entry)
                c_tab = catalog_tariff_as_table(cand_artifact.spec.runtime.model, c_cat_entry)
                b_roll = compute_rollup(baseline_events, b_tab)
                c_roll = compute_rollup(candidate_events, c_tab)
                baseline_catalog_cost = b_roll.cost_per_run_usd
                candidate_catalog_cost = c_roll.cost_per_run_usd
                delta_catalog_cost = candidate_catalog_cost - baseline_catalog_cost
        except FileNotFoundError as exc:
            catalog_warnings.append(str(exc))
        except yaml.YAMLError as exc:
            catalog_warnings.append(f"pricing catalog YAML parse error: {exc}")
        except ValidationError as exc:
            catalog_warnings.append(f"invalid pricing catalog YAML: {exc}")
        except OSError as exc:
            catalog_warnings.append(f"pricing catalog I/O error: {exc}")

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
        pricing_hints=tuple(pricing_hints),
        catalog_enabled=catalog_enabled,
        catalog_version=catalog_version,
        baseline_catalog_slot_id=baseline_catalog_slot_id,
        candidate_catalog_slot_id=candidate_catalog_slot_id,
        baseline_catalog_cost_per_run_usd=baseline_catalog_cost,
        candidate_catalog_cost_per_run_usd=candidate_catalog_cost,
        delta_catalog_cost_per_run_usd=delta_catalog_cost,
        catalog_warnings=tuple(catalog_warnings),
        pricing_warnings=tuple(pricing_warnings),
    )


def _compute_promotion_policy_result(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    action: Literal["promote", "rollback"],
    release_id: str,
    environment: str,
    window: str,
) -> tuple[PolicyResult, str | None, str]:
    """Evaluate policy for promote/rollback without mutating the ledger."""
    _, target_artifact = _load_release_or_error(storage, release_id, role="target")
    agent_id = target_artifact.spec.agent.agent_id
    current_release_id = storage.get_promoted_release_id(agent_id, environment)
    active_policy = storage.get_active_policy() or default_policy()

    if action == "promote" and not current_release_id:
        return (
            PolicyResult(
                passed=True,
                reasons=["first promotion: no promoted baseline for agent/environment"],
            ),
            current_release_id,
            agent_id,
        )

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
    return (diff.policy, current_release_id, agent_id)


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

    policy_result, current_release_id, agent_id = _compute_promotion_policy_result(
        cfg=cfg,
        storage=storage,
        action=action,
        release_id=release_id,
        environment=environment,
        window=window,
    )

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
        if action == "promote":
            _dispatch_webhook_safe(
                storage,
                "promote.blocked",
                {
                    "action_id": action_id,
                    "release_id": release_id,
                    "agent_id": agent_id,
                    "environment": environment,
                    "window": window,
                    "actor": actor,
                    "reason": reason,
                    "baseline_release_id": current_release_id,
                    "policy_reasons": list(policy_result.reasons),
                },
            )
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
    _dispatch_webhook_safe(
        storage,
        "promote.succeeded" if action == "promote" else "rollback.succeeded",
        {
            "action_id": action_id,
            "release_id": release_id,
            "agent_id": agent_id,
            "environment": environment,
            "window": window,
            "actor": actor,
            "reason": reason,
            "baseline_release_id": current_release_id,
        },
    )
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


def _dispatch_webhook_safe(storage: Storage, event: str, data: dict) -> None:
    """Best-effort fan-out. Webhook errors must never break the promote / rollback path."""
    try:
        # Local import keeps ``operations`` free of an httpx import at module load.
        from flightdeck.webhooks import dispatch_event

        dispatch_event(storage, event, data)
    except Exception:
        logging.getLogger(__name__).warning(
            "Webhook dispatch failed for event=%s", event, exc_info=True
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
    _approval_confirm: bool = False,
) -> ActionOutcome:
    if cfg.promotion_requires_approval and not _approval_confirm:
        raise OperationError(
            "Workspace promotion_requires_approval=true: use promote-request then promote-confirm "
            "(HTTP POST /v1/promote/request and POST /v1/promote/confirm)."
        )
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


def request_promotion(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    release_id: str,
    environment: str,
    window: str,
    reason: str,
    actor: str,
) -> PromotionRequestRecord:
    if not cfg.promotion_requires_approval:
        raise OperationError(
            "promotion_requires_approval is false in flightdeck.yaml; use direct `release promote` "
            "or set promotion_requires_approval: true to use the approval workflow."
        )
    if not reason.strip():
        raise OperationError("Reason is required for promotion requests.")

    policy_result, current_release_id, agent_id = _compute_promotion_policy_result(
        cfg=cfg,
        storage=storage,
        action="promote",
        release_id=release_id,
        environment=environment,
        window=window,
    )
    if not policy_result.passed:
        raise OperationError(
            "Policy does not allow this promotion; request not recorded. Reasons: "
            + "; ".join(policy_result.reasons)
        )

    request_id = f"prq_{uuid4().hex[:12]}"
    record = PromotionRequestRecord(
        request_id=request_id,
        status="pending",
        release_id=release_id,
        agent_id=agent_id,
        environment=environment,
        window=window,
        reason=reason,
        actor=actor,
        baseline_release_id=current_release_id,
        policy_result=policy_result,
        created_at=utc_now(),
    )
    storage.insert_promotion_request(record)
    return record


def confirm_promotion_request(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    request_id: str,
    approval_reason: str,
    actor: str,
) -> ActionOutcome:
    if not approval_reason.strip():
        raise OperationError("approval_reason is required for promote-confirm.")
    pending = storage.get_promotion_request(request_id)
    if pending is None or pending.status != "pending":
        raise OperationError("Unknown promotion request_id or request is not pending.")

    combined_reason = f"{pending.reason} | approval: {approval_reason}"
    outcome = promote_release(
        cfg=cfg,
        storage=storage,
        release_id=pending.release_id,
        environment=pending.environment,
        window=pending.window,
        reason=combined_reason,
        actor=actor,
        _approval_confirm=True,
    )
    if outcome.promoted_pointer_changed:
        storage.mark_promotion_request_completed(request_id, completed_action_id=outcome.action_id)
    return outcome


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


def query_run_events_page(
    *,
    cfg: WorkspaceConfig,
    storage: Storage,
    release_id: str,
    window: str,
    environment: str | None,
    tenant_id: str | None,
    task_id: str | None,
    trace_id: str | None = None,
    session_id: str | None = None,
    span_id: str | None = None,
    offset: int = 0,
    limit: int,
) -> dict[str, object]:
    """Read-only slice of run events for forensics (newest-first truncation)."""
    if not storage.get_release(release_id):
        raise OperationError(f"Unknown release: {release_id}")
    env = environment or cfg.default_environment
    tid = (trace_id or "").strip() or None
    sid = (session_id or "").strip() or None
    spid = (span_id or "").strip() or None
    off = max(0, int(offset))
    try:
        delta = parse_window(window)
    except ValueError as e:
        raise OperationError(str(e)) from e
    until = utc_now()
    since = until - delta
    events = storage.query_runs(
        release_id,
        since,
        until,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=env,
        trace_id=tid,
        session_id=sid,
        span_id=spid,
    )
    events_sorted = sorted(events, key=lambda e: e.timestamp, reverse=True)
    lim = max(1, min(500, limit))
    page = events_sorted[off : off + lim]
    return {
        "release_id": release_id,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "filters": {
            "environment": env,
            "tenant_id": tenant_id,
            "task_id": task_id,
            "trace_id": tid,
            "session_id": sid,
            "span_id": spid,
        },
        "offset": off,
        "limit": lim,
        "matched_total": len(events),
        "returned": len(page),
        "truncated": off + len(page) < len(events),
        "events": [e.model_dump(mode="json") for e in page],
    }


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
