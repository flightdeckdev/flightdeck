from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest

from flightdeck.models import RunEvent, RunEventModelUsage, RunEventUsage
from flightdeck.sdk.client import AsyncFlightdeckClient, FlightdeckClient


def test_flightdeck_client_ingest_uses_post_v1_events() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/events"
        captured["body"] = json.loads(request.content.decode("utf-8"))
        events = captured["body"]["events"]
        assert isinstance(events, list)
        return httpx.Response(200, json={"inserted": len(events)})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://flightdeck.test") as http:
        client = FlightdeckClient("http://flightdeck.test", client=http)
        now = datetime.now(tz=timezone.utc)
        event = RunEvent(
            timestamp=now,
            agent_id="agent_support",
            release_id="rel_test",
            run_id="run_sdk_mock",
            tenant_id="tenant_acme",
            task_id="task_1",
            environment="local",
            usage=RunEventUsage(
                model=RunEventModelUsage(
                    provider="openai",
                    model="gpt-4.1-mini",
                    input_tokens=10,
                    output_tokens=5,
                )
            ),
        )
        inserted = client.ingest_run_events([event])
        assert inserted == 1

    body = captured["body"]
    assert isinstance(body, dict)
    events_out = body["events"]
    assert len(events_out) == 1
    assert events_out[0]["run_id"] == "run_sdk_mock"
    assert events_out[0]["api_version"] == "v1"


def _event(run_id: str) -> RunEvent:
    now = datetime.now(tz=timezone.utc)
    return RunEvent(
        timestamp=now,
        agent_id="agent_support",
        release_id="rel_test",
        run_id=run_id,
        tenant_id="tenant_acme",
        task_id="task_1",
        environment="local",
        usage=RunEventUsage(
            model=RunEventModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=10,
                output_tokens=5,
            )
        ),
    )


def test_flightdeck_client_sends_bearer_when_api_token_set() -> None:
    seen_auth: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"inserted": 1})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://flightdeck.test") as http:
        client = FlightdeckClient("http://flightdeck.test", client=http, api_token="secret")
        client.ingest_run_events([_event("tok-run")])
    assert seen_auth == ["Bearer secret"]


def test_flightdeck_client_list_releases_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/releases"
        return httpx.Response(200, json={"releases": []})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://flightdeck.test") as http:
        client = FlightdeckClient("http://flightdeck.test", client=http)
        assert client.list_releases() == {"releases": []}


def test_flightdeck_client_get_workspace_get() -> None:
    payload = {
        "api_version": "v1",
        "kind": "WorkspacePublic",
        "promotion_requires_approval": True,
        "pricing_catalog_configured": False,
        "server_version": "9.9.9",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/workspace"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://flightdeck.test") as http:
        client = FlightdeckClient("http://flightdeck.test", client=http)
        assert client.get_workspace() == payload


def test_flightdeck_client_promote_raises_on_policy_block() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/promote"
        return httpx.Response(
            409,
            json={
                "detail": {
                    "message": "Promotion blocked by policy.",
                    "outcome": {
                        "promoted_pointer_changed": False,
                        "policy": {"passed": False, "reasons": ["candidate cost exceeds max"]},
                    },
                }
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://flightdeck.test") as http:
        client = FlightdeckClient("http://flightdeck.test", client=http)
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            client.post_promote(
                release_id="rel_blocked",
                environment="local",
                window="7d",
                reason="policy check",
            )

    assert excinfo.value.response.status_code == 409


def test_flightdeck_client_ingest_batch_chunks_payload() -> None:
    seen_lengths: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen_lengths.append(len(body["events"]))
        return httpx.Response(200, json={"inserted": len(body["events"])})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://flightdeck.test") as http:
        client = FlightdeckClient("http://flightdeck.test", client=http)
        inserted = client.ingest_run_events_batch([_event("r1"), _event("r2"), _event("r3")], chunk_size=2)
        assert inserted == 3
    assert seen_lengths == [2, 1]


def test_flightdeck_client_retries_request_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(200, json={"inserted": 1})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://flightdeck.test") as http:
        client = FlightdeckClient(
            "http://flightdeck.test",
            client=http,
            max_retries=1,
            retry_backoff_s=0.0,
        )
        assert client.ingest_run_events([_event("retry-run")]) == 1
    assert attempts == 2


def test_flightdeck_client_invalid_chunk_size() -> None:
    client = FlightdeckClient("http://flightdeck.test")
    try:
        with pytest.raises(ValueError, match="chunk_size must be > 0"):
            client.ingest_run_events_batch([], chunk_size=0)
    finally:
        client.close()


def test_async_flightdeck_client_ingest_batch() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"inserted": len(body["events"])})

    async def _run() -> int:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://flightdeck.test") as http:
            client = AsyncFlightdeckClient("http://flightdeck.test", client=http)
            return await client.ingest_run_events_batch([_event("a1"), _event("a2"), _event("a3")], chunk_size=2)

    inserted = asyncio.run(_run())
    assert inserted == 3
    assert calls == 2
