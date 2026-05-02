"""Map OpenAI Chat Completions API responses to RunEvent (optional ``openai`` extra for callers)."""

from __future__ import annotations

from typing import Any

from flightdeck.integrations.common import make_run_end_event
from flightdeck.models import RunEvent


def token_totals_from_openai_chat_completion(response: object) -> tuple[int, int, int, str]:
    """Return ``(input_tokens, output_tokens, cached_input_tokens, model_id)`` from a completion response.

    Uses duck typing so tests do not require the ``openai`` package. Missing usage yields zeros
    and ``"unknown"`` for the model.
    """
    model = getattr(response, "model", None) or "unknown"
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0, str(model)
    inp = int(getattr(usage, "prompt_tokens", 0) or 0)
    out = int(getattr(usage, "completion_tokens", 0) or 0)
    cached = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = int(getattr(details, "cached_tokens", 0) or 0)
    return inp, out, cached, str(model)


def run_event_from_openai_chat_completion(
    response: object,
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
    """Build a ``RunEvent`` from an OpenAI chat completion ``response`` object."""
    inp, out, cached, model = token_totals_from_openai_chat_completion(response)
    merged = {"integration": "openai_chat", **(labels or {})}
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
