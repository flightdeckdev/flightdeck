from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from flightdeck.operations import ActionOutcome, OperationError, compute_diff, promote_release, rollback_release
from flightdeck.server.routes.common import ensure_app_state

router = APIRouter()

_LOCAL_CLIENT_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


class DiffRequest(BaseModel):
    baseline_release_id: str
    candidate_release_id: str
    window: str
    tenant_id: str | None = None
    task_id: str | None = None
    environment: str | None = None


class ActionRequest(BaseModel):
    release_id: str
    environment: str
    window: str
    reason: str = Field(min_length=1)
    actor: str = "http"


def _raise_bad_request(exc: OperationError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _action_body(outcome: ActionOutcome) -> dict[str, object]:
    return {
        "action_id": outcome.action_id,
        "action": outcome.action,
        "release_id": outcome.release_id,
        "agent_id": outcome.agent_id,
        "environment": outcome.environment,
        "baseline_release_id": outcome.baseline_release_id,
        "promoted_pointer_changed": outcome.promoted_pointer_changed,
        "policy": outcome.policy.model_dump(mode="json"),
    }


def _raise_policy_blocked(action: str, outcome: ActionOutcome) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "message": f"{action.capitalize()} blocked by policy.",
            "outcome": _action_body(outcome),
        },
    )


def _require_mutation_access(request: Request) -> None:
    ensure_app_state(request)
    expected_token: str | None = request.app.state.local_api_token
    auth_header = request.headers.get("authorization", "")
    if expected_token:
        if auth_header != f"Bearer {expected_token}":
            raise HTTPException(status_code=401, detail="Missing or invalid API token for mutation route.")
        return

    host = request.client.host if request.client else ""
    if host not in _LOCAL_CLIENT_HOSTS:
        raise HTTPException(
            status_code=403,
            detail="Mutation routes are restricted to local clients unless FLIGHTDECK_LOCAL_API_TOKEN is configured.",
        )


@router.post("/v1/diff")
def post_diff(request: Request, req: DiffRequest) -> dict[str, object]:
    cfg, storage = ensure_app_state(request)
    try:
        result = compute_diff(
            cfg=cfg,
            storage=storage,
            baseline_release_id=req.baseline_release_id,
            candidate_release_id=req.candidate_release_id,
            window=req.window,
            environment=req.environment,
            tenant_id=req.tenant_id,
            task_id=req.task_id,
        )
    except OperationError as exc:
        raise _raise_bad_request(exc) from exc

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
            # Per-side unit prices for the resolved model (None when the model
            # is missing from the pricing table; cost rollup will surface its
            # own KeyError before reaching here when events are present).
            "prices": {
                "baseline_input_usd_per_1k_tokens": result.baseline_input_usd_per_1k_tokens,
                "baseline_output_usd_per_1k_tokens": result.baseline_output_usd_per_1k_tokens,
                "baseline_cached_input_usd_per_1k_tokens": result.baseline_cached_input_usd_per_1k_tokens,
                "candidate_input_usd_per_1k_tokens": result.candidate_input_usd_per_1k_tokens,
                "candidate_output_usd_per_1k_tokens": result.candidate_output_usd_per_1k_tokens,
                "candidate_cached_input_usd_per_1k_tokens": result.candidate_cached_input_usd_per_1k_tokens,
            },
            # Diagnostic strings when a release's resolved model has no entry
            # in its pricing table; the cost rollup still raises if such a
            # model appears in events. These are informational only and do
            # not flip policy.
            "warnings": list(result.pricing_warnings),
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


@router.post("/v1/promote")
def post_promote(request: Request, req: ActionRequest) -> dict[str, object]:
    _require_mutation_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        outcome = promote_release(
            cfg=cfg,
            storage=storage,
            release_id=req.release_id,
            environment=req.environment,
            window=req.window,
            reason=req.reason,
            actor=req.actor,
        )
    except OperationError as exc:
        raise _raise_bad_request(exc) from exc

    if not outcome.policy.passed:
        raise _raise_policy_blocked("promotion", outcome)

    return _action_body(outcome)


@router.post("/v1/rollback")
def post_rollback(request: Request, req: ActionRequest) -> dict[str, object]:
    _require_mutation_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        outcome = rollback_release(
            cfg=cfg,
            storage=storage,
            release_id=req.release_id,
            environment=req.environment,
            window=req.window,
            reason=req.reason,
            actor=req.actor,
        )
    except OperationError as exc:
        raise _raise_bad_request(exc) from exc

    if not outcome.policy.passed:
        raise _raise_policy_blocked("rollback", outcome)

    return _action_body(outcome)
