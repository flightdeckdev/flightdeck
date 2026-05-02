"""CrewAI-friendly RunEvent construction without importing CrewAI at module import time.

Callers typically invoke :func:`run_event_from_crew_token_totals` after ``Crew.kickoff()`` with
token counts taken from CrewAI logs or a custom callback, until a stable usage API is available
across versions.
"""

from __future__ import annotations

from typing import Any

from flightdeck.integrations.common import make_run_end_event
from flightdeck.models import RunEvent


def run_event_from_crew_token_totals(
    *,
    agent_id: str,
    release_id: str,
    run_id: str,
    tenant_id: str,
    task_id: str,
    environment: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    crew_name: str | None = None,
    labels: dict[str, Any] | None = None,
    trace_id: str | None = None,
    latency_ms: int | None = None,
    success: bool = True,
    error_type: str | None = None,
) -> RunEvent:
    """Build a ``RunEvent`` from aggregated LLM totals after a CrewAI run."""
    merged: dict[str, Any] = {"integration": "crewai", **(labels or {})}
    if crew_name:
        merged["crew.name"] = crew_name
    return make_run_end_event(
        agent_id=agent_id,
        release_id=release_id,
        run_id=run_id,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=environment,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
        trace_id=trace_id,
        labels=merged,
    )
