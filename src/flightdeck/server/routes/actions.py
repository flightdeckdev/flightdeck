from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from flightdeck.operations import (
    ActionOutcome,
    OperationError,
    compute_diff,
    confirm_promotion_request,
    diff_outcome_to_public_dict,
    promote_release,
    request_promotion,
    rollback_release,
)
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


class PromotionRequestCreate(BaseModel):
    release_id: str
    environment: str
    window: str
    reason: str = Field(min_length=1)
    actor: str = "http"


class PromotionConfirmRequest(BaseModel):
    request_id: str
    approval_reason: str = Field(min_length=1)
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

    return diff_outcome_to_public_dict(result)


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


@router.post("/v1/promote/request")
def post_promote_request(request: Request, req: PromotionRequestCreate) -> dict[str, object]:
    _require_mutation_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        record = request_promotion(
            cfg=cfg,
            storage=storage,
            release_id=req.release_id,
            environment=req.environment,
            window=req.window,
            reason=req.reason,
            actor=req.actor,
        )
    except OperationError as exc:
        msg = str(exc)
        if msg.startswith("Policy does not allow"):
            raise HTTPException(
                status_code=409,
                detail={"message": msg},
            ) from exc
        raise _raise_bad_request(exc) from exc

    return {
        "request_id": record.request_id,
        "status": record.status,
        "release_id": record.release_id,
        "agent_id": record.agent_id,
        "environment": record.environment,
        "window": record.window,
        "baseline_release_id": record.baseline_release_id,
        "policy": record.policy_result.model_dump(mode="json"),
        "created_at": record.created_at.isoformat(),
    }


@router.post("/v1/promote/confirm")
def post_promote_confirm(request: Request, req: PromotionConfirmRequest) -> dict[str, object]:
    _require_mutation_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        outcome = confirm_promotion_request(
            cfg=cfg,
            storage=storage,
            request_id=req.request_id,
            approval_reason=req.approval_reason,
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
