"""ASGI middleware for response-side debugging affordances.

Adds two response headers on every HTTP request:

- ``X-Request-Id``: per-request UUID, used for log correlation. If the
  client already sent the header on the request, that value is echoed
  back (lets the client choose its own trace id). Otherwise a fresh
  ``uuid4().hex`` is generated.
- ``X-FlightDeck-Server-Version``: the package version
  (``flightdeck.__version__``). Lets clients (CLI, SDK, dashboards)
  detect server / client skew without a round-trip to ``/health``.

The middleware is intentionally tiny and side-effect-free apart from
the two header writes. It does not log, does not allocate per-request
beyond the UUID, and never raises.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from flightdeck import __version__ as _SERVER_VERSION

REQUEST_ID_HEADER = "X-Request-Id"
SERVER_VERSION_HEADER = "X-FlightDeck-Server-Version"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Stamp every response with a request id and the server version."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming and incoming.strip() else uuid.uuid4().hex
        # Make the id available to downstream handlers (logging, audit
        # rows, future webhook delivery_id correlation).
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[SERVER_VERSION_HEADER] = _SERVER_VERSION
        return response
