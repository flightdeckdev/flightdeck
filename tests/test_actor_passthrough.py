"""Tests for HTTP identity passthrough into the audit ledger.

The route handlers prefer ``X-FlightDeck-Actor`` and ``X-Forwarded-User``
headers (in that order) over the JSON body ``actor`` field, so a
reverse-proxy / SSO layer can authoritatively stamp the audit ledger
without trusting caller-controlled request bodies.

See ``src/flightdeck/server/routes/actions.py::resolve_actor``.
"""

from __future__ import annotations

from fastapi import Request
from starlette.datastructures import Headers

from flightdeck.server.routes.actions import (
    _ACTOR_HEADERS,
    resolve_actor,
)


def _request_with_headers(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    request = Request(scope)
    # Starlette parses scope['headers'] lazily; force materialisation so the
    # resolve_actor lookup hits a populated Headers instance.
    request._headers = Headers(scope=scope)  # noqa: SLF001  (test-only)
    return request


def test_resolve_actor_falls_back_to_body_when_no_headers() -> None:
    req = _request_with_headers({})
    assert resolve_actor(req, "ci-bot") == "ci-bot"


def test_resolve_actor_prefers_x_flightdeck_actor_over_body() -> None:
    req = _request_with_headers({"X-FlightDeck-Actor": "jane.doe"})
    assert resolve_actor(req, "http") == "jane.doe"


def test_resolve_actor_uses_x_forwarded_user_when_explicit_header_missing() -> None:
    req = _request_with_headers({"X-Forwarded-User": "alice@example.com"})
    assert resolve_actor(req, "http") == "alice@example.com"


def test_resolve_actor_x_flightdeck_actor_wins_over_x_forwarded_user() -> None:
    req = _request_with_headers(
        {
            "X-FlightDeck-Actor": "explicit.actor",
            "X-Forwarded-User": "proxy.actor",
        }
    )
    assert resolve_actor(req, "http") == "explicit.actor"


def test_resolve_actor_ignores_whitespace_only_headers() -> None:
    req = _request_with_headers(
        {"X-FlightDeck-Actor": "   ", "X-Forwarded-User": "real.user"}
    )
    assert resolve_actor(req, "http") == "real.user"


def test_resolve_actor_strips_surrounding_whitespace() -> None:
    req = _request_with_headers({"X-FlightDeck-Actor": "  spaced.user  "})
    assert resolve_actor(req, "http") == "spaced.user"


def test_actor_header_precedence_is_documented_in_constant() -> None:
    # The order in _ACTOR_HEADERS is part of the documented contract: the
    # explicit FlightDeck header must win over the de-facto reverse-proxy
    # one, so operators can override at the FlightDeck layer.
    assert _ACTOR_HEADERS == ("X-FlightDeck-Actor", "X-Forwarded-User")
