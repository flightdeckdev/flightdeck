from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

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


def _to_prometheus_text(counters: dict, schema_version: int) -> str:
    """Format ledger counters as Prometheus text exposition format (version 0.0.4)."""
    lines: list[str] = []

    def _metric(name: str, description: str, value: int | float, labels: dict[str, str] | None = None) -> None:
        lines.append(f"# HELP {name} {description}")
        lines.append(f"# TYPE {name} gauge")
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{label_str}}} {value}")
        else:
            lines.append(f"{name} {value}")
        lines.append("")

    _metric(
        "flightdeck_releases_total",
        "Registered release artifacts",
        counters.get("releases_total", 0),
    )
    _metric(
        "flightdeck_run_events_total",
        "Ingested RunEvent records",
        counters.get("run_events_total", 0),
    )
    _metric(
        "flightdeck_promoted_pointers_total",
        "Active promotion pointers",
        counters.get("promoted_pointers_total", 0),
    )
    _metric(
        "flightdeck_actions_total",
        "Ledger actions (promote + rollback)",
        counters.get("actions_total", 0),
    )

    # actions_by_type — one labeled series per action type
    actions_by_action: dict[str, int] = counters.get("actions_by_action", {})
    lines.append("# HELP flightdeck_actions_by_type Ledger actions broken down by type")
    lines.append("# TYPE flightdeck_actions_by_type gauge")
    for action_name, action_count in actions_by_action.items():
        lines.append(f'flightdeck_actions_by_type{{action="{action_name}"}} {action_count}')
    lines.append("")

    _metric(
        "flightdeck_pricing_tables_total",
        "Imported pricing tables",
        counters.get("pricing_tables_total", 0),
    )
    _metric(
        "flightdeck_schema_version",
        "Current ledger schema migration version",
        schema_version,
    )

    return "\n".join(lines)


@router.get("/metrics")
def get_prometheus_metrics(request: Request) -> PlainTextResponse:
    """Prometheus text exposition format scrape endpoint (no new dependencies).

    Returns metrics in ``text/plain; version=0.0.4; charset=utf-8`` as required by the
    Prometheus scrape protocol. Same Bearer / loopback gate as ``GET /v1/metrics``.
    Configure Prometheus with ``metrics_path: /metrics`` and
    ``bearer_token: <FLIGHTDECK_LOCAL_API_TOKEN>`` when a token is set.
    """
    _, storage = ensure_app_state(request)
    counters = storage.get_ledger_counters()
    generated_at = utc_now().isoformat()
    body = f"# generated_at {generated_at}\n\n" + _to_prometheus_text(counters, LATEST_SCHEMA_MIGRATION_VERSION)
    return PlainTextResponse(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
