"""Load bundled pricing YAML from the wheel and seed a new workspace."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from flightdeck.models import PricingTable
from flightdeck.storage import Storage

BUNDLED_PRICING_VERSION = "flightdeck-bundled-2026-05"
BUNDLED_TABLE_FILENAMES = ("openai.yaml", "anthropic.yaml", "google.yaml")
BUNDLED_CATALOG_FILENAME = "catalog.yaml"
DEFAULT_CATALOG_RELATIVE_PATH = ".flightdeck/pricing-catalog.yaml"


def _read_resource_text(name: str) -> str:
    root = resources.files("flightdeck.bundled_pricing")
    return root.joinpath(name).read_text(encoding="utf-8")


def load_bundled_pricing_tables() -> list[PricingTable]:
    tables: list[PricingTable] = []
    for name in BUNDLED_TABLE_FILENAMES:
        data: Any = yaml.safe_load(_read_resource_text(name))
        tables.append(PricingTable.model_validate(data))
    return tables


def load_bundled_catalog_yaml_text() -> str:
    return _read_resource_text(BUNDLED_CATALOG_FILENAME)


def bootstrap_bundled_pricing(
    *,
    storage: Storage,
    actor: str,
    catalog_dest: Path,
) -> None:
    """Import bundled pricing tables and write the catalog file to ``catalog_dest``."""
    catalog_dest.parent.mkdir(parents=True, exist_ok=True)
    catalog_dest.write_text(load_bundled_catalog_yaml_text(), encoding="utf-8", newline="\n")

    for table in load_bundled_pricing_tables():
        storage.insert_pricing_table(table, replace=False, actor=actor, reason=None)
