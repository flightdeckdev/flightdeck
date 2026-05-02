"""Optional workspace pricing catalog for cross-vendor comparable cost rollups.

A catalog maps (provider, pricing_version, model) to a *catalog slot* with
operator-defined USD-per-1k-token tariffs. Re-costing each side's run events
with those tariffs yields ``catalog_*`` metrics on diffs without changing
existing per-table ``metrics.*`` semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from flightdeck.models import PricingEntry, PricingTable


class PricingCatalogMapping(BaseModel):
    provider: str
    pricing_version: str
    model: str
    catalog_slot_id: str


class PricingCatalogTariff(BaseModel):
    """Comparable USD rates for one catalog slot (same units as :class:`PricingEntry`)."""

    input_usd_per_1k_tokens: float = Field(ge=0)
    output_usd_per_1k_tokens: float = Field(ge=0)
    cached_input_usd_per_1k_tokens: float | None = Field(default=None, ge=0)


class PricingCatalog(BaseModel):
    api_version: Literal["v1"] = "v1"
    kind: Literal["PricingCatalog"] = "PricingCatalog"

    catalog_version: str
    mappings: list[PricingCatalogMapping] = Field(default_factory=list)
    tariffs: dict[str, PricingCatalogTariff] = Field(default_factory=dict)


def load_pricing_catalog(path: str | Path) -> PricingCatalog:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Pricing catalog not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f) or {}
    return PricingCatalog.model_validate(data)


def resolve_catalog_slot_id(
    catalog: PricingCatalog,
    *,
    provider: str,
    pricing_version: str,
    model: str,
) -> str | None:
    for m in catalog.mappings:
        if m.provider == provider and m.pricing_version == pricing_version and m.model == model:
            return m.catalog_slot_id
    return None


def resolve_catalog_pricing_entry(
    catalog: PricingCatalog,
    *,
    provider: str,
    pricing_version: str,
    model: str,
) -> tuple[PricingEntry | None, str | None]:
    """Return a :class:`PricingEntry` for ``model`` using catalog tariffs, or (None, reason)."""
    slot = resolve_catalog_slot_id(catalog, provider=provider, pricing_version=pricing_version, model=model)
    if slot is None:
        return None, f"no catalog mapping for {provider}/{pricing_version} model={model!r}"
    tariff = catalog.tariffs.get(slot)
    if tariff is None:
        return None, f"catalog slot {slot!r} has no tariffs entry"
    entry = PricingEntry(
        model=model,
        input_usd_per_1k_tokens=tariff.input_usd_per_1k_tokens,
        output_usd_per_1k_tokens=tariff.output_usd_per_1k_tokens,
        cached_input_usd_per_1k_tokens=tariff.cached_input_usd_per_1k_tokens,
    )
    return entry, None


def catalog_tariff_as_table(model: str, entry: PricingEntry) -> PricingTable:
    """Single-model table for :func:`flightdeck.ledger.compute_rollup`."""
    return PricingTable(
        provider="_flightdeck_catalog",
        pricing_version="_synthetic",
        entries=[
            PricingEntry(
                model=model,
                input_usd_per_1k_tokens=entry.input_usd_per_1k_tokens,
                output_usd_per_1k_tokens=entry.output_usd_per_1k_tokens,
                cached_input_usd_per_1k_tokens=entry.cached_input_usd_per_1k_tokens,
            )
        ],
    )
