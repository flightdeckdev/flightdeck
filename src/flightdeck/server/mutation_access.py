"""Shared access control for HTTP routes that touch the workspace ledger or read its contents."""

from __future__ import annotations

from fastapi import HTTPException, Request

from flightdeck.server.routes.common import ensure_app_state

_LOCAL_CLIENT_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def _normalized_local_api_token(request: Request) -> str:
    raw: str | None = getattr(request.app.state, "local_api_token", None)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _bearer_matches(request: Request, expected: str) -> bool:
    auth_header = request.headers.get("authorization", "")
    return auth_header == f"Bearer {expected}"


def require_protected_read_access(request: Request) -> None:
    """When ``FLIGHTDECK_LOCAL_API_TOKEN`` is set, require Bearer on read ``GET /v1/*`` routes.

    With no token configured, read routes stay open (network placement is the operator's
    boundary). With a token, every caller must send ``Authorization: Bearer <token>`` —
    same header as ledger writes — so shared clusters and port-forwards do not leak the
    audit trail to unauthenticated peers.
    """
    ensure_app_state(request)
    expected = _normalized_local_api_token(request)
    if not expected:
        return
    if not _bearer_matches(request, expected):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API token for read route.",
        )


def require_ledger_write_access(request: Request) -> None:
    """Require loopback client or Bearer token (same model as promote/rollback).

    When ``FLIGHTDECK_LOCAL_API_TOKEN`` is set, every matching route must send
    ``Authorization: Bearer <token>``. When it is unset, only loopback callers may
    mutate the ledger, so binding ``flightdeck serve --host 0.0.0.0`` does not leave
    event ingest open to the whole network.
    """
    ensure_app_state(request)
    expected = _normalized_local_api_token(request)
    if expected:
        if not _bearer_matches(request, expected):
            raise HTTPException(status_code=401, detail="Missing or invalid API token for mutation route.")
        return

    host = request.client.host if request.client else ""
    if host not in _LOCAL_CLIENT_HOSTS:
        raise HTTPException(
            status_code=403,
            detail="Mutation routes are restricted to local clients unless FLIGHTDECK_LOCAL_API_TOKEN is configured.",
        )
