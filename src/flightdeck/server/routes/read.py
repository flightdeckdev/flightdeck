from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from flightdeck import __version__ as flightdeck_version
from flightdeck.models import PromotionRequestRecord, WorkspacePublic
from flightdeck.operations import OperationError, list_timeline, query_run_events_page
from flightdeck.server.routes.common import ensure_app_state

router = APIRouter()


@router.get("/v1/workspace")
def get_workspace(request: Request) -> WorkspacePublic:
    """Non-secret workspace flags for operators and the web UI."""
    cfg, _ = ensure_app_state(request)
    return WorkspacePublic.from_workspace_config(cfg, server_version=flightdeck_version)


@router.get("/v1/releases")
def get_releases(request: Request) -> dict[str, list[dict[str, object]]]:
    _, storage = ensure_app_state(request)
    timeline = list_timeline(storage=storage, action_limit=0)
    return {"releases": timeline.releases}


@router.get("/v1/promoted")
def get_promoted(request: Request) -> dict[str, list[dict[str, str]]]:
    _, storage = ensure_app_state(request)
    timeline = list_timeline(storage=storage, action_limit=0)
    return {"promoted": timeline.promoted}


@router.get("/v1/actions")
def get_actions(
    request: Request,
    agent_id: str | None = Query(default=None, alias="agent"),
    environment: str | None = Query(default=None, alias="env"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, list[dict[str, object]]]:
    _, storage = ensure_app_state(request)
    timeline = list_timeline(storage=storage, agent_id=agent_id, environment=environment, action_limit=limit)
    return {"actions": timeline.actions}


def _promotion_request_to_dict(r: PromotionRequestRecord) -> dict[str, object]:
    return {
        "request_id": r.request_id,
        "status": r.status,
        "release_id": r.release_id,
        "agent_id": r.agent_id,
        "environment": r.environment,
        "window": r.window,
        "reason": r.reason,
        "actor": r.actor,
        "baseline_release_id": r.baseline_release_id,
        "policy": r.policy_result.model_dump(mode="json"),
        "created_at": r.created_at.isoformat(),
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "completed_action_id": r.completed_action_id,
    }


@router.get("/v1/promotion-requests")
def get_promotion_requests(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, list[dict[str, object]]]:
    _, storage = ensure_app_state(request)
    rows = storage.list_promotion_requests(status=status, limit=limit)
    return {"requests": [_promotion_request_to_dict(r) for r in rows]}


@router.get("/v1/runs")
def get_runs(
    request: Request,
    release_id: str = Query(..., min_length=1),
    window: str = Query(..., min_length=1),
    environment: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    cfg, storage = ensure_app_state(request)
    try:
        return query_run_events_page(
            cfg=cfg,
            storage=storage,
            release_id=release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
            limit=limit,
        )
    except OperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
