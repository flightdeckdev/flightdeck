"""Tests for the request-context middleware.

The middleware stamps every response with ``X-Request-Id`` and
``X-FlightDeck-Server-Version``. Verify (a) a fresh id is generated when
the client did not send one, (b) the client id is echoed back when it
did, and (c) the version header always matches the package version.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flightdeck import __version__
from flightdeck.server.middleware import (
    REQUEST_ID_HEADER,
    SERVER_VERSION_HEADER,
    RequestContextMiddleware,
)


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_request_id_generated_when_client_omits_header() -> None:
    client = _client()
    resp = client.get("/ping")
    assert resp.status_code == 200
    got = resp.headers.get(REQUEST_ID_HEADER)
    assert got is not None
    # uuid4().hex is exactly 32 lowercase hex chars.
    assert len(got) == 32
    assert all(c in "0123456789abcdef" for c in got)


def test_client_supplied_request_id_is_echoed() -> None:
    client = _client()
    resp = client.get("/ping", headers={REQUEST_ID_HEADER: "trace-abc-123"})
    assert resp.status_code == 200
    assert resp.headers[REQUEST_ID_HEADER] == "trace-abc-123"


def test_whitespace_only_client_id_is_replaced() -> None:
    client = _client()
    resp = client.get("/ping", headers={REQUEST_ID_HEADER: "   "})
    assert resp.status_code == 200
    got = resp.headers[REQUEST_ID_HEADER]
    assert got.strip() != ""
    assert got != "   "


def test_server_version_header_matches_package_version() -> None:
    client = _client()
    resp = client.get("/ping")
    assert resp.headers[SERVER_VERSION_HEADER] == __version__


def test_request_id_is_unique_across_requests() -> None:
    client = _client()
    a = client.get("/ping").headers[REQUEST_ID_HEADER]
    b = client.get("/ping").headers[REQUEST_ID_HEADER]
    assert a != b
