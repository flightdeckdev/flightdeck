from __future__ import annotations

import json
from datetime import datetime, timezone

from flightdeck.models import RunEvent, RunEventModelUsage, RunEventUsage
from flightdeck.sdk.http_common import (
    ClientHttpCore,
    diff_request_body,
    events_ingest_json,
    promote_confirm_body,
    runs_list_params,
)


def test_client_http_core_headers() -> None:
    c = ClientHttpCore("http://example.com/", None)
    assert c.abs_url("/v1/health") == "http://example.com/v1/health"
    assert c.auth_headers() == {}
    assert c.json_headers() == {"Content-Type": "application/json"}

    t = ClientHttpCore("http://x", "tok")
    assert t.auth_headers() == {"Authorization": "Bearer tok"}
    assert t.json_headers()["Authorization"] == "Bearer tok"


def test_diff_request_body_includes_nones() -> None:
    b = diff_request_body(
        baseline_release_id="a",
        candidate_release_id="b",
        window="7d",
        environment=None,
        tenant_id=None,
        task_id=None,
    )
    assert b["environment"] is None
    assert b["tenant_id"] is None


def test_events_ingest_json_round_trip() -> None:
    now = datetime.now(tz=timezone.utc)
    ev = RunEvent(
        timestamp=now,
        agent_id="a",
        release_id="r",
        run_id="run1",
        tenant_id="t",
        task_id="k",
        environment="local",
        usage=RunEventUsage(
            model=RunEventModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=1,
                output_tokens=2,
            )
        ),
    )
    payload = events_ingest_json([ev])
    assert payload is not None
    assert json.loads(json.dumps(payload))["events"][0]["run_id"] == "run1"


def test_events_ingest_json_empty() -> None:
    assert events_ingest_json([]) is None


def test_promote_confirm_body_shape() -> None:
    b = promote_confirm_body(request_id="rid", approval_reason="ok", actor="me")
    assert b["request_id"] == "rid"
    assert b["actor"] == "me"


def test_runs_list_params_optional_keys() -> None:
    p = runs_list_params(
        release_id="rel",
        window="1d",
        environment="prod",
        tenant_id="tn",
        task_id="tk",
        trace_id="tr",
        session_id="sn",
        span_id="sp",
        offset=5,
        limit=10,
    )
    assert p["environment"] == "prod"
    assert p["trace_id"] == "tr"
