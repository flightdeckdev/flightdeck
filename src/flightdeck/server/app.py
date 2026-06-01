from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from flightdeck.config import load_config
from flightdeck.server.middleware import RequestContextMiddleware
from flightdeck.server.routes import include_routes
from flightdeck.storage import storage_from_config


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cfg = load_config()
        storage = storage_from_config(cfg)
        storage.migrate()
        app.state.cfg = cfg
        app.state.storage = storage
        app.state.local_api_token = os.environ.get("FLIGHTDECK_LOCAL_API_TOKEN")
        yield

    app = FastAPI(title="FlightDeck", version="local", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    include_routes(app)
    static_dir = Path(__file__).resolve().parent / "static"
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="ui-assets")

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        """Liveness plus safe API auth hints (no secrets).

        ``mutation_auth`` applies to **POST /v1/events** as well as promote/rollback:
        ``bearer`` when ``FLIGHTDECK_LOCAL_API_TOKEN`` is set (Bearer required for those
        routes from any client host), else ``loopback`` (writes allowed only from
        loopback unless the token is configured). ``read_auth`` applies to **GET /v1/***
        (workspace, metrics, runs, …): ``bearer`` when the same token is set (Bearer
        required), else ``open``. ``POST /v1/diff`` is not gated by these fields.
        """
        token = getattr(request.app.state, "local_api_token", None)
        token_s = token.strip() if isinstance(token, str) else ""
        mutation_auth = "bearer" if token_s else "loopback"
        read_auth = "bearer" if token_s else "open"
        return {"status": "ok", "mutation_auth": mutation_auth, "read_auth": read_auth}

    @app.get("/")
    def ui_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/flightdeck-icon.png")
    def ui_app_icon() -> FileResponse:
        """Shipped UI favicon / sidebar mark (copied from ``web/public`` at build time)."""
        path = static_dir / "flightdeck-icon.png"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="UI icon not found (rebuild web bundle)")
        return FileResponse(path, media_type="image/png")

    return app
