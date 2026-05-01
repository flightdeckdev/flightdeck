from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from flightdeck.models import WorkspaceConfig


DEFAULT_CONFIG_FILENAME = "flightdeck.yaml"


def config_path(start_dir: str | Path = ".") -> Path:
    base = Path(start_dir).resolve()
    return base / DEFAULT_CONFIG_FILENAME


def load_config(path: str | Path = DEFAULT_CONFIG_FILENAME) -> WorkspaceConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Workspace config not found: {p}. Run `flightdeck init`.")

    data: Any
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return WorkspaceConfig.model_validate(data)


def write_default_config(path: str | Path = DEFAULT_CONFIG_FILENAME) -> Path:
    cfg = WorkspaceConfig()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(cfg.model_dump(mode="json"), f, sort_keys=False)

    return p

