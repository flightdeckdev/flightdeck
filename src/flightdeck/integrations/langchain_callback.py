"""LangChain Core callback handler that aggregates token usage into a RunEvent.

Requires the ``integrations-langchain`` extra (``langchain-core``).

Import this submodule only when that dependency is installed:

``from flightdeck.integrations.langchain_callback import FlightDeckLangChainCallbackHandler``
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from flightdeck.integrations.common import make_run_end_event
from flightdeck.models import RunEvent


def _usage_from_llm_result(response: Any) -> tuple[int, int, int, str]:
    """Best-effort token totals and model name from an LLMResult-like object."""
    inp = out = cached = 0
    model = "unknown"
    llm_output = getattr(response, "llm_output", None) or {}
    if isinstance(llm_output, dict):
        tu = llm_output.get("token_usage") or {}
        inp = int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0)
        out = int(tu.get("completion_tokens") or tu.get("output_tokens") or 0)
        model = str(llm_output.get("model_name") or model)
    gens = getattr(response, "generations", None) or []
    for gen_list in gens:
        for gen in gen_list:
            msg = getattr(gen, "message", None)
            meta = getattr(msg, "usage_metadata", None) if msg is not None else None
            if isinstance(meta, dict):
                inp += int(meta.get("input_tokens") or 0)
                out += int(meta.get("output_tokens") or 0)
                itd = meta.get("input_token_details")
                if isinstance(itd, dict):
                    cached += int(itd.get("cache_read") or 0)
                model = str(meta.get("model_name") or meta.get("model") or model)
    return inp, out, cached, model


class FlightDeckLangChainCallbackHandler(BaseCallbackHandler):
    """Accumulate LLM token usage across steps; materialize with :meth:`to_run_event`."""

    def __init__(
        self,
        *,
        agent_id: str,
        release_id: str,
        run_id: str,
        tenant_id: str,
        task_id: str,
        environment: str,
        provider: str = "openai",
        labels: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._agent_id = agent_id
        self._release_id = release_id
        self._run_id = run_id
        self._tenant_id = tenant_id
        self._task_id = task_id
        self._environment = environment
        self._provider = provider
        self._labels = {"integration": "langchain", **(labels or {})}
        self._inp = 0
        self._out = 0
        self._cached = 0
        self._model = "unknown"

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:  # noqa: ANN401
        di, do, dc, model = _usage_from_llm_result(response)
        self._inp += di
        self._out += do
        self._cached += dc
        if model != "unknown":
            self._model = model

    def to_run_event(
        self,
        *,
        latency_ms: int | None = None,
        success: bool = True,
        error_type: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> RunEvent:
        return make_run_end_event(
            agent_id=self._agent_id,
            release_id=self._release_id,
            run_id=self._run_id,
            tenant_id=self._tenant_id,
            task_id=self._task_id,
            environment=self._environment,
            provider=self._provider,
            model=self._model,
            input_tokens=self._inp,
            output_tokens=self._out,
            cached_input_tokens=self._cached,
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
            trace_id=trace_id,
            session_id=session_id,
            labels=dict(self._labels),
        )
