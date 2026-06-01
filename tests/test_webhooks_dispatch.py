from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from flightdeck.storage import Storage
from flightdeck.webhooks import dispatch_event, sign_payload


def _storage_with_webhooks(tmp_path: Path, webhooks: list[dict[str, Any]]) -> Storage:
    s = Storage(str(tmp_path / "flightdeck.db"))
    s.migrate()
    for i, w in enumerate(webhooks):
        s.insert_webhook(
            webhook_id=w.get("webhook_id", f"wh_{i}"),
            url=w["url"],
            events=w["events"],
            secret=w["secret"],
            description=None,
            created_at=f"2026-05-31T00:00:{i:02d}+00:00",
        )
    return s


def _install_transport(
    monkeypatch, handler: Any, sleeps: list[float] | None = None
) -> None:
    """Replace ``httpx.Client`` with one wired to a MockTransport (and stub sleep)."""
    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("flightdeck.webhooks.httpx.Client", fake_client)
    if sleeps is not None:
        monkeypatch.setattr("flightdeck.webhooks.time.sleep", lambda s: sleeps.append(s))


def test_dispatch_event_signs_body_and_sends_headers(tmp_path: Path, monkeypatch) -> None:
    secret = "shhh-test-secret-1234567890"
    s = _storage_with_webhooks(
        tmp_path,
        [{"url": "https://hooks.example.com/x", "events": ["promote.succeeded"], "secret": secret}],
    )

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, text="ok")

    _install_transport(monkeypatch, handler, sleeps=[])

    results = dispatch_event(s, "promote.succeeded", {"release_id": "rel_1"})
    assert len(results) == 1
    assert results[0]["status"] == "delivered"
    assert results[0]["attempts"] == 1
    assert len(captured) == 1

    req = captured[0]
    assert req.url.host == "hooks.example.com"
    assert req.headers["X-FlightDeck-Event"] == "promote.succeeded"
    assert req.headers["X-FlightDeck-Delivery"]
    sig = req.headers["X-FlightDeck-Signature"]
    assert sig.startswith("sha256=")
    # Independently verify the signature against the exact transmitted body.
    assert sig == sign_payload(secret, req.content)
    # Payload envelope is intact.
    payload = json.loads(req.content)
    assert payload["event"] == "promote.succeeded"
    assert payload["data"]["release_id"] == "rel_1"


def test_dispatch_event_retries_on_5xx_and_gives_up_after_three(tmp_path: Path, monkeypatch) -> None:
    s = _storage_with_webhooks(
        tmp_path,
        [{"url": "https://hooks.example.com/x", "events": ["promote.succeeded"], "secret": "s"}],
    )
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, text="boom")

    sleeps: list[float] = []
    _install_transport(monkeypatch, handler, sleeps=sleeps)

    results = dispatch_event(s, "promote.succeeded", {})
    assert calls["n"] == 3
    assert results[0]["status"] == "failed"
    assert results[0]["attempts"] == 3
    assert results[0]["error"] == "HTTP 500"
    # Backoff happens between attempts: 1 s, then 2 s (no sleep after the final attempt).
    assert sleeps == [1, 2]


def test_dispatch_event_recovers_after_initial_failure(tmp_path: Path, monkeypatch) -> None:
    s = _storage_with_webhooks(
        tmp_path,
        [{"url": "https://hooks.example.com/x", "events": ["promote.succeeded"], "secret": "s"}],
    )
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="try again")
        return httpx.Response(202, text="ok")

    _install_transport(monkeypatch, handler, sleeps=[])

    results = dispatch_event(s, "promote.succeeded", {})
    assert results[0]["status"] == "delivered"
    assert results[0]["attempts"] == 2
    assert results[0]["http_status"] == 202


def test_dispatch_event_only_fires_for_subscribed_webhooks(tmp_path: Path, monkeypatch) -> None:
    s = _storage_with_webhooks(
        tmp_path,
        [
            {
                "webhook_id": "wh_only_rollback",
                "url": "https://a.example.com",
                "events": ["rollback.succeeded"],
                "secret": "s1",
            },
            {
                "webhook_id": "wh_both",
                "url": "https://b.example.com",
                "events": ["promote.succeeded", "rollback.succeeded"],
                "secret": "s2",
            },
        ],
    )
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200)

    _install_transport(monkeypatch, handler, sleeps=[])

    results = dispatch_event(s, "promote.succeeded", {})
    assert seen == ["b.example.com"]
    assert [r["webhook_id"] for r in results] == ["wh_both"]


def test_dispatch_event_skips_disabled_webhooks(tmp_path: Path, monkeypatch) -> None:
    s = _storage_with_webhooks(
        tmp_path,
        [{"url": "https://a.example.com", "events": ["promote.succeeded"], "secret": "s"}],
    )
    with s.connect() as conn:
        conn.execute("UPDATE webhooks SET enabled = 0")

    called = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200)

    _install_transport(monkeypatch, handler, sleeps=[])
    results = dispatch_event(s, "promote.succeeded", {})
    assert results == []
    assert called["n"] == 0


def test_dispatch_event_swallows_transport_errors(tmp_path: Path, monkeypatch) -> None:
    s = _storage_with_webhooks(
        tmp_path,
        [{"url": "https://a.example.com", "events": ["promote.succeeded"], "secret": "s"}],
    )

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    _install_transport(monkeypatch, handler, sleeps=[])
    # Must not raise.
    results = dispatch_event(s, "promote.succeeded", {})
    assert results[0]["status"] == "failed"
    assert results[0]["attempts"] == 3
    assert "ConnectError" in (results[0]["error"] or "")
