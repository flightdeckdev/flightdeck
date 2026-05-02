"""LangChain callback tests (requires ``integrations-ci`` / ``integrations-langchain``)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("langchain_core")

from flightdeck.integrations.langchain_callback import (  # noqa: E402
    FlightDeckLangChainCallbackHandler,
)


def test_langchain_callback_accumulates() -> None:
    h = FlightDeckLangChainCallbackHandler(
        agent_id="a",
        release_id="r",
        run_id="run_lc",
        tenant_id="t",
        task_id="k",
        environment="local",
    )
    llm_output = {"token_usage": {"prompt_tokens": 5, "completion_tokens": 2}, "model_name": "m1"}
    resp = SimpleNamespace(generations=[], llm_output=llm_output)
    h.on_llm_end(resp)
    ev = h.to_run_event()
    assert ev.usage.model.input_tokens == 5
    assert ev.usage.model.output_tokens == 2
    assert ev.usage.model.model == "m1"
