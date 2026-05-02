"""Unit tests for flightdeck.integrations (no optional third-party deps for core cases)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from flightdeck.integrations import common
from flightdeck.integrations import anthropic_messages
from flightdeck.integrations import crewai_bridge
from flightdeck.integrations import openai_agents
from flightdeck.integrations import openai_chat


def test_make_run_end_event_minimal() -> None:
    ts = datetime(2026, 1, 2, tzinfo=timezone.utc)
    ev = common.make_run_end_event(
        agent_id="a",
        release_id="r",
        run_id="run1",
        tenant_id="t",
        task_id="k",
        environment="local",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=10,
        output_tokens=3,
        timestamp=ts,
    )
    assert ev.api_version == "v1"
    assert ev.type == "run_end"
    assert ev.timestamp == ts
    assert ev.usage.model.input_tokens == 10
    assert ev.usage.model.output_tokens == 3
    assert ev.usage.model.cached_input_tokens == 0


def test_temporal_labels() -> None:
    assert common.temporal_labels(workflow_id="wf1") == {"temporal.workflow_id": "wf1"}
    assert common.temporal_labels(workflow_id="wf1", workflow_run_id="wr1")[
        "temporal.run_id"
    ] == "wr1"


def test_openai_chat_completion_usage() -> None:
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=40,
        prompt_tokens_details=SimpleNamespace(cached_tokens=20),
    )
    resp = SimpleNamespace(model="gpt-4.1-mini", usage=usage)
    inp, out, cached, model = openai_chat.token_totals_from_openai_chat_completion(resp)
    assert (inp, out, cached, model) == (100, 40, 20, "gpt-4.1-mini")
    ev = openai_chat.run_event_from_openai_chat_completion(
        resp,
        agent_id="agent_support",
        release_id="rel_x",
        run_id="run_openai",
        tenant_id="tenant_a",
        task_id="t1",
        environment="local",
    )
    assert ev.usage.model.provider == "openai"
    assert ev.labels.get("integration") == "openai_chat"


def test_anthropic_message_usage() -> None:
    usage = SimpleNamespace(input_tokens=50, output_tokens=25, cache_read_input_tokens=10)
    msg = SimpleNamespace(model="claude-3-5-haiku-20241022", usage=usage)
    inp, out, cached, model = anthropic_messages.token_totals_from_anthropic_message(msg)
    assert (inp, out, cached) == (50, 25, 10)
    ev = anthropic_messages.run_event_from_anthropic_message(
        msg,
        agent_id="agent_support",
        release_id="rel_x",
        run_id="run_ant",
        tenant_id="tenant_a",
        task_id="t1",
        environment="local",
    )
    assert ev.usage.model.provider == "anthropic"
    assert ev.labels.get("integration") == "anthropic_messages"


def test_openai_agents_result_dict_usage() -> None:
    result = SimpleNamespace(usage={"input_tokens": 9, "output_tokens": 2, "model": "gpt-4o"})
    ev = openai_agents.run_event_from_openai_agents_result(
        result,
        agent_id="a",
        release_id="r",
        run_id="run_ag",
        tenant_id="t",
        task_id="k",
        environment="local",
    )
    assert ev.usage.model.input_tokens == 9
    assert ev.usage.model.output_tokens == 2


def test_crewai_bridge() -> None:
    ev = crewai_bridge.run_event_from_crew_token_totals(
        agent_id="a",
        release_id="r",
        run_id="run_c",
        tenant_id="t",
        task_id="k",
        environment="local",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=200,
        output_tokens=50,
        crew_name="research",
    )
    assert ev.labels.get("integration") == "crewai"
    assert ev.labels.get("crew.name") == "research"
