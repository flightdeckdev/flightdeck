from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from flightdeck.models import utc_now
from flightdeck.server.mutation_access import require_protected_read_access
from flightdeck.server.routes.common import ensure_app_state
from flightdeck.storage import LATEST_SCHEMA_MIGRATION_VERSION

router = APIRouter(dependencies=[Depends(require_protected_read_access)])


@router.get("/v1/metrics")
def get_metrics(request: Request) -> dict[str, object]:
    """Read-only aggregate counts for operators (JSON; no Prometheus text format)."""
    _, storage = ensure_app_state(request)
    return {
        "counters": storage.get_ledger_counters(),
        "schema_version": LATEST_SCHEMA_MIGRATION_VERSION,
        "generated_at": utc_now().isoformat(),
    }
