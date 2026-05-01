from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from flightdeck.config import load_config
from flightdeck.models import RunEvent
from flightdeck.storage import Storage


class IngestEventsRequest(BaseModel):
    events: list[dict[str, Any]] = Field(min_length=1)


def create_app() -> FastAPI:
    app = FastAPI(title="FlightDeck", version="local")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/events")
    def ingest_events(req: IngestEventsRequest) -> dict[str, int]:
        cfg = load_config()
        storage = Storage(cfg.db_path)
        storage.migrate()

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

    return app
