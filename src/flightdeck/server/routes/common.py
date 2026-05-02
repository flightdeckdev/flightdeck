from __future__ import annotations

import os
from fastapi import Request

from flightdeck.config import load_config
from flightdeck.models import WorkspaceConfig
from flightdeck.storage import Storage


def ensure_app_state(request: Request) -> tuple[WorkspaceConfig, Storage]:
    cfg: WorkspaceConfig | None = getattr(request.app.state, "cfg", None)
    storage: Storage | None = getattr(request.app.state, "storage", None)
    if cfg is not None and storage is not None:
        return cfg, storage

    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()
    request.app.state.cfg = cfg
    request.app.state.storage = storage
    if not hasattr(request.app.state, "local_api_token"):
        request.app.state.local_api_token = os.environ.get("FLIGHTDECK_LOCAL_API_TOKEN")
    return cfg, storage
