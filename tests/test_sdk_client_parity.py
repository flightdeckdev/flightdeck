"""Sync vs async SDK clients must issue identical HTTP shapes (shared ``http_common``)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import httpx

from flightdeck.models import RunEvent, RunEventModelUsage, RunEventUsage
from flightdeck.sdk.client import AsyncFlightdeckClient, FlightdeckClient


def _snap(request: httpx.Request) -> tuple[str, str, tuple[tuple[str, str], ...], str]:
    q = tuple(sorted(request.url.params.multi_items()))
    body = request.content.decode("utf-8") if request.content else ""
    return (request.method, request.url.path, q, body)


def _event() -> RunEvent:
    now = datetime.now(tz=timezone.utc)
    return RunEvent(
        timestamp=now,
        agent_id="a",
        release_id="r",
        run_id="run_parity",
        tenant_id="t",
        task_id="k",
        environment="local",
        usage=RunEventUsage(
            model=RunEventModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=1,
                output_tokens=1,
            )
        ),
    )


def test_parity_list_runs_params_and_headers() -> None:
    sync_captured: list[tuple[str, str, tuple[tuple[str, str], ...], str]] = []

    def sync_handler(request: httpx.Request) -> httpx.Response:
        sync_captured.append(_snap(request))
        return httpx.Response(200, json={"runs": []})

    transport = httpx.MockTransport(sync_handler)
    with httpx.Client(transport=transport, base_url="http://fd.test") as http:
        c = FlightdeckClient("http://fd.test", client=http, api_token="abc")
        c.list_runs(
            release_id="rel1",
            window="7d",
            environment="local",
            tenant_id="t1",
            task_id=None,
            trace_id="tr1",
            session_id=None,
            span_id=None,
            offset=2,
            limit=50,
        )
        c.close()

    async_captured: list[tuple[str, str, tuple[tuple[str, str], ...], str]] = []

    def async_handler(request: httpx.Request) -> httpx.Response:
        async_captured.append(_snap(request))
        return httpx.Response(200, json={"runs": []})

    async def _go() -> None:
        t = httpx.MockTransport(async_handler)
        async with httpx.AsyncClient(transport=t, base_url="http://fd.test") as http:
            ac = AsyncFlightdeckClient("http://fd.test", client=http, api_token="abc")
            await ac.list_runs(
                release_id="rel1",
                window="7d",
                environment="local",
                tenant_id="t1",
                task_id=None,
                trace_id="tr1",
                session_id=None,
                span_id=None,
                offset=2,
                limit=50,
            )
            await ac.aclose()

    asyncio.run(_go())
    assert sync_captured == async_captured
    method, path, query, _body = sync_captured[0]
    assert method == "GET"
    assert path == "/v1/runs"
    assert ("trace_id", "tr1") in query


def test_parity_post_diff_json_body() -> None:
    sync_captured: list[str] = []

    def sh(request: httpx.Request) -> httpx.Response:
        sync_captured.append(request.content.decode("utf-8"))
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(sh), base_url="http://fd.test") as http:
        FlightdeckClient("http://fd.test", client=http).post_diff(
            baseline_release_id="b1",
            candidate_release_id="c1",
            window="24h",
            tenant_id="tn",
        )

    async_captured: list[str] = []

    def ah(request: httpx.Request) -> httpx.Response:
        async_captured.append(request.content.decode("utf-8"))
        return httpx.Response(200, json={})

    async def _go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(ah), base_url="http://fd.test") as http:
            await AsyncFlightdeckClient("http://fd.test", client=http).post_diff(
                baseline_release_id="b1",
                candidate_release_id="c1",
                window="24h",
                tenant_id="tn",
            )

    asyncio.run(_go())
    assert json.loads(sync_captured[0]) == json.loads(async_captured[0])


def test_parity_ingest_events_payload() -> None:
    ev = _event()
    sync_body: list[dict] = []

    def sh(request: httpx.Request) -> httpx.Response:
        sync_body.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"inserted": 1})

    with httpx.Client(transport=httpx.MockTransport(sh), base_url="http://fd.test") as http:
        FlightdeckClient("http://fd.test", client=http).ingest_run_events([ev])

    async_body: list[dict] = []

    def ah(request: httpx.Request) -> httpx.Response:
        async_body.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"inserted": 1})

    async def _go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(ah), base_url="http://fd.test") as http:
            await AsyncFlightdeckClient("http://fd.test", client=http).ingest_run_events([ev])

    asyncio.run(_go())
    assert sync_body == async_body
