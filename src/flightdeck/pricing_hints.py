"""Non-blocking pricing diagnostics (version skew hints, model name hints)."""

from __future__ import annotations

from flightdeck.models import PricingTable, ReleasePricingReference
from flightdeck.storage import Storage


def _other_versions_for_provider(storage: Storage, provider: str, current_version: str) -> list[str]:
    return [v for v in storage.list_pricing_versions(provider) if v != current_version]


def _similar_model_hints(table: PricingTable, model: str, *, limit: int = 5) -> list[str]:
    if not model:
        return []
    ml = model.lower()
    hints: list[str] = []
    for e in table.entries:
        el = e.model.lower()
        if el == ml:
            continue
        if ml in el or el in ml:
            hints.append(e.model)
        if len(hints) >= limit:
            break
    return hints


def collect_pricing_skew_hints(
    storage: Storage,
    *,
    role: str,
    ref: ReleasePricingReference,
    model: str,
    table: PricingTable,
    model_in_table: bool,
) -> list[str]:
    """Return human-readable hints; never raises."""
    hints: list[str] = []
    others = _other_versions_for_provider(storage, ref.provider, ref.pricing_version)
    if len(others) >= 1:
        sample = ", ".join(others[:5])
        more = f" (+{len(others) - 5} more)" if len(others) > 5 else ""
        hints.append(
            f"{role}: provider {ref.provider!r} has other imported pricing_version values "
            f"besides {ref.pricing_version!r}: {sample}{more}. "
            f"Confirm the release pins the table you intend."
        )
    if not model_in_table and model:
        sim = _similar_model_hints(table, model)
        if sim:
            hints.append(f"{role}: table has no exact model {model!r}; similar names: {', '.join(sim)}")
    return hints
