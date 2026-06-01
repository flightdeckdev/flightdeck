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
from flightdeck.server.mutation_access import require_ledger_write_access
from flightdeck.server.routes.common import ensure_app_state

router = APIRouter()


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


# Header names checked, in order, before falling back to the request body.
# - X-FlightDeck-Actor: explicit, intended for callers that want to set the
#   audit actor without owning the request body shape (e.g. GitHub Actions
#   wrappers, CI gates with environment-derived identity).
# - X-Forwarded-User: the de-facto convention used by oauth2-proxy /
#   Pomerium / Authelia / Cloudflare Access / nginx auth_request and most
#   reverse proxies in front of a private service. This is the same shape
#   enterprise SSO setups already emit.
# The first non-empty header wins. The body actor is the final fallback,
# and the "http" default in the Pydantic models is a last-resort sentinel
# so the audit row is never blank.
_ACTOR_HEADERS = ("X-FlightDeck-Actor", "X-Forwarded-User")


def resolve_actor(request: Request, body_actor: str) -> str:
    """Return the effective audit actor for a mutation request.

    Header precedence allows a reverse-proxy / SSO layer to authoritatively
    set the identity that lands in the audit ledger without trusting the
    caller-controlled request body. Caller-side identity (CLI scripts,
    bots, automation) still flows through the body.
    """
    for header in _ACTOR_HEADERS:
        value = request.headers.get(header)
        if value and value.strip():
            return value.strip()
    return body_actor


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
    require_ledger_write_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        outcome = promote_release(
            cfg=cfg,
            storage=storage,
            release_id=req.release_id,
            environment=req.environment,
            window=req.window,
            reason=req.reason,
            actor=resolve_actor(request, req.actor),
        )
    except OperationError as exc:
        raise _raise_bad_request(exc) from exc

    if not outcome.policy.passed:
        raise _raise_policy_blocked("promotion", outcome)

    return _action_body(outcome)


@router.post("/v1/promote/request")
def post_promote_request(request: Request, req: PromotionRequestCreate) -> dict[str, object]:
    require_ledger_write_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        record = request_promotion(
            cfg=cfg,
            storage=storage,
            release_id=req.release_id,
            environment=req.environment,
            window=req.window,
            reason=req.reason,
            actor=resolve_actor(request, req.actor),
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
    require_ledger_write_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        outcome = confirm_promotion_request(
            cfg=cfg,
            storage=storage,
            request_id=req.request_id,
            approval_reason=req.approval_reason,
            actor=resolve_actor(request, req.actor),
        )
    except OperationError as exc:
        raise _raise_bad_request(exc) from exc

    if not outcome.policy.passed:
        raise _raise_policy_blocked("promotion", outcome)

    return _action_body(outcome)


@router.post("/v1/rollback")
def post_rollback(request: Request, req: ActionRequest) -> dict[str, object]:
    require_ledger_write_access(request)
    cfg, storage = ensure_app_state(request)
    try:
        outcome = rollback_release(
            cfg=cfg,
            storage=storage,
            release_id=req.release_id,
            environment=req.environment,
            window=req.window,
            reason=req.reason,
            actor=resolve_actor(request, req.actor),
        )
    except OperationError as exc:
        raise _raise_bad_request(exc) from exc

    if not outcome.policy.passed:
        raise _raise_policy_blocked("rollback", outcome)

    return _action_body(outcome)
