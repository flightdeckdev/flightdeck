from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from flightdeck.models import RunEvent, RunEventModelUsage, RunEventUsage
from flightdeck.sdk.client import FlightdeckClient


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
