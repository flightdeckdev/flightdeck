from __future__ import annotations

from fastapi import FastAPI

from flightdeck.server.routes.actions import router as actions_router
from flightdeck.server.routes.ingest import router as ingest_router
from flightdeck.server.routes.metrics import router as metrics_router
from flightdeck.server.routes.read import router as read_router
from flightdeck.server.routes.webhooks import router as webhooks_router


def include_routes(app: FastAPI) -> None:
    app.include_router(ingest_router)
    app.include_router(read_router)
    app.include_router(metrics_router)
    app.include_router(actions_router)
    app.include_router(webhooks_router)
