"""Age and staleness helpers for ``flightdeck-bundled-YYYY-MM`` pricing snapshots."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

# Bundled snapshot ids use the first day of the labeled month as the freshness anchor.
BUNDLED_PRICING_VERSION_RE = re.compile(r"^flightdeck-bundled-(\d{4})-(\d{2})$")

# Default max age before CLI / diff warn (days since anchor).
DEFAULT_BUNDLED_PRICING_MAX_AGE_DAYS = 90


def pricing_stale_check_date() -> date:
    """UTC date used for staleness checks (patch in tests)."""
    return datetime.now(timezone.utc).date()


def is_flightdeck_bundled_pricing_version(pricing_version: str) -> bool:
    return bundled_pricing_anchor_date(pricing_version) is not None


def bundled_pricing_anchor_date(pricing_version: str) -> date | None:
    m = BUNDLED_PRICING_VERSION_RE.match(pricing_version.strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12):
        return None
    return date(year, month, 1)


def bundled_pricing_age_days(pricing_version: str, *, today: date) -> int | None:
    anchor = bundled_pricing_anchor_date(pricing_version)
    if anchor is None:
        return None
    return (today - anchor).days


def bundled_pricing_stale_warning(
    pricing_version: str,
    *,
    today: date | None = None,
    max_age_days: int = DEFAULT_BUNDLED_PRICING_MAX_AGE_DAYS,
    role: str | None = None,
) -> str | None:
    """
    Return a human-readable warning if this bundled snapshot is older than ``max_age_days``.

    ``role`` is optional ("baseline" / "candidate") for diff copy.
    """
    anchor = bundled_pricing_anchor_date(pricing_version)
    if anchor is None:
        return None
    day = today if today is not None else pricing_stale_check_date()
    age = (day - anchor).days
    if age <= max_age_days:
        return None
    prefix = f"{role} " if role else ""
    return (
        f"{prefix}pricing_version {pricing_version!r} is a FlightDeck bundled snapshot from "
        f"{anchor.isoformat()} (~{age} days old). List prices drift; run `flightdeck pricing import` "
        f"with authoritative YAML or upgrade to a newer `flightdeck-ai` minor for refreshed bundled tables."
    )
