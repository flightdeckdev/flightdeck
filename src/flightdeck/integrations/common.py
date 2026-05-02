"""Shared helpers for building v1 RunEvent payloads (no third-party imports)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flightdeck.models import RunEvent, RunEventMetrics, RunEventModelUsage, RunEventRequest, RunEventUsage


def make_run_end_event(
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
    latency_ms: int | None = None,
    success: bool = True,
    error_type: str | None = None,
    trace_id: str | None = None,
    session_id: str | None = None,
    span_id: str | None = None,
    labels: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
    workspace_id: str = "ws_local",
) -> RunEvent:
    """Construct a type=run_end RunEvent with model usage (stable v1 wire shape)."""
    req: RunEventRequest | None = None
    if trace_id is not None or session_id is not None or span_id is not None:
        req = RunEventRequest(session_id=session_id, trace_id=trace_id, span_id=span_id)
    return RunEvent(
        timestamp=timestamp or datetime.now(timezone.utc),
        workspace_id=workspace_id,
        agent_id=agent_id,
        release_id=release_id,
        run_id=run_id,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=environment,
        request=req,
        metrics=RunEventMetrics(
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
        ),
        usage=RunEventUsage(
            model=RunEventModelUsage(
                provider=provider,
                model=model,
                input_tokens=max(0, int(input_tokens)),
                output_tokens=max(0, int(output_tokens)),
                cached_input_tokens=max(0, int(cached_input_tokens)),
            ),
        ),
        labels=dict(labels or {}),
    )


def temporal_labels(*, workflow_id: str, workflow_run_id: str | None = None) -> dict[str, str]:
    """Suggested labels when emitting from Temporal (no temporalio import)."""
    out = {"temporal.workflow_id": workflow_id}
    if workflow_run_id:
        out["temporal.run_id"] = workflow_run_id
    return out
