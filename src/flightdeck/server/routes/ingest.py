from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from flightdeck.models import RunEvent
from flightdeck.server.routes.common import ensure_app_state

router = APIRouter()


class IngestEventsRequest(BaseModel):
    events: list[dict[str, Any]] = Field(min_length=1)


@router.post("/v1/events")
def ingest_events(request: Request, req: IngestEventsRequest) -> dict[str, int]:
    _, storage = ensure_app_state(request)

    events: list[RunEvent] = []
    for item in req.events:
        av = item.get("api_version", "v1")
        if av != "v1":
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported api_version for POST /v1/events: {av!r} (only 'v1' is accepted).",
            )
        try:
            events.append(RunEvent.model_validate(item))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid RunEvent: {e}") from e

    inserted = storage.insert_run_events(events)
    return {"inserted": inserted}
