from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from flightdeck.config import load_config
from flightdeck.server.routes import include_routes
from flightdeck.storage import Storage


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cfg = load_config()
        storage = Storage(cfg.db_path)
        storage.migrate()
        app.state.cfg = cfg
        app.state.storage = storage
        app.state.local_api_token = os.environ.get("FLIGHTDECK_LOCAL_API_TOKEN")
        yield

    app = FastAPI(title="FlightDeck", version="local", lifespan=lifespan)
    include_routes(app)
    static_dir = Path(__file__).resolve().parent / "static"
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="ui-assets")

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        """Liveness plus safe mutation-auth hints (no secrets)."""
        token = getattr(request.app.state, "local_api_token", None)
        token_s = token.strip() if isinstance(token, str) else ""
        mutation_auth = "bearer" if token_s else "loopback"
        return {"status": "ok", "mutation_auth": mutation_auth}

    @app.get("/")
    def ui_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app
