from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from flightdeck.operations import OperationError, compute_diff, promote_release, rollback_release
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
