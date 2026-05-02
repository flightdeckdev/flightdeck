"""Helpers for OpenAI Agents SDK runs (optional ``integrations-openai-agents`` extra).

The Agents SDK surface evolves; these helpers use duck typing on the **result** object returned
from a run helper (for example ``Runner.run``) and optional context attributes.
"""

from __future__ import annotations

from typing import Any

from flightdeck.integrations.common import make_run_end_event
from flightdeck.models import RunEvent


def _gather_usage_dict(obj: object) -> dict[str, Any]:
    """Best-effort extraction of usage-like mappings from SDK result/context objects."""
    for attr in ("usage", "token_usage", "metrics"):
        got = getattr(obj, attr, None)
        if isinstance(got, dict):
            return got
    # Some versions nest usage on context
    ctx = getattr(obj, "context", None)
    if ctx is not None:
        for attr in ("usage", "token_usage"):
            got = getattr(ctx, attr, None)
            if isinstance(got, dict):
                return got
    return {}


def token_totals_from_openai_agents_result(result: object) -> tuple[int, int, int, str]:
    """Return ``(input_tokens, output_tokens, cached_input_tokens, model_guess)``."""
    usage = _gather_usage_dict(result)
    inp = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    out = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    cached = int(usage.get("cached_input_tokens") or usage.get("cached_tokens") or 0)
    model = str(usage.get("model") or getattr(result, "model", None) or "unknown")
    return inp, out, cached, model


def run_event_from_openai_agents_result(
    result: object,
    *,
    agent_id: str,
    release_id: str,
    run_id: str,
    tenant_id: str,
    task_id: str,
    environment: str,
    labels: dict[str, Any] | None = None,
    trace_id: str | None = None,
    session_id: str | None = None,
    latency_ms: int | None = None,
    success: bool = True,
    error_type: str | None = None,
) -> RunEvent:
    """Build a ``RunEvent`` after an OpenAI Agents SDK run completes."""
    inp, out, cached, model = token_totals_from_openai_agents_result(result)
    merged = {"integration": "openai_agents", **(labels or {})}
    return make_run_end_event(
        agent_id=agent_id,
        release_id=release_id,
        run_id=run_id,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=environment,
        provider="openai",
        model=model,
        input_tokens=inp,
        output_tokens=out,
        cached_input_tokens=cached,
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
        trace_id=trace_id,
        session_id=session_id,
        labels=merged,
    )
