from __future__ import annotations

from fastapi import APIRouter, Query, Request

from flightdeck.operations import list_timeline
from flightdeck.server.routes.common import ensure_app_state

router = APIRouter()


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
