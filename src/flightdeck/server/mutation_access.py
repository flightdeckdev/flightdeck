"""Shared access control for HTTP routes that append to or mutate the workspace ledger."""

from __future__ import annotations

from fastapi import HTTPException, Request

from flightdeck.server.routes.common import ensure_app_state

_LOCAL_CLIENT_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def require_ledger_write_access(request: Request) -> None:
    """Require loopback client or Bearer token (same model as promote/rollback).

    When ``FLIGHTDECK_LOCAL_API_TOKEN`` is set, every matching route must send
    ``Authorization: Bearer <token>``. When it is unset, only loopback callers may
    mutate the ledger, so binding ``flightdeck serve --host 0.0.0.0`` does not leave
    event ingest open to the whole network.
    """
    ensure_app_state(request)
    expected_token: str | None = getattr(request.app.state, "local_api_token", None)
    auth_header = request.headers.get("authorization", "")
    if expected_token:
        if auth_header != f"Bearer {expected_token}":
            raise HTTPException(status_code=401, detail="Missing or invalid API token for mutation route.")
        return

    host = request.client.host if request.client else ""
    if host not in _LOCAL_CLIENT_HOSTS:
        raise HTTPException(
            status_code=403,
            detail="Mutation routes are restricted to local clients unless FLIGHTDECK_LOCAL_API_TOKEN is configured.",
        )
