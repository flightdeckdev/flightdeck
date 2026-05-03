"""Shared HTTP helpers for sync and async FlightDeck SDK clients."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from flightdeck.models import RunEvent


@dataclass(frozen=True)
class HttpRetryPolicy:
    """Retry loop parameters (sync uses ``time.sleep``, async ``asyncio.sleep``)."""

    max_retries: int
    backoff_s: float


class ClientHttpCore:
    """URL and header helpers shared by ``FlightdeckClient`` and ``AsyncFlightdeckClient``."""

    __slots__ = ("_api_token", "_base_url")

    def __init__(self, base_url: str, api_token: str | None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token

    def abs_url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def auth_headers(self) -> dict[str, str]:
        if self._api_token:
            return {"Authorization": f"Bearer {self._api_token}"}
        return {}

    def json_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", **self.auth_headers()}


def actions_params(*, agent_id: str | None, environment: str | None, limit: int) -> dict[str, str | int]:
    params: dict[str, str | int] = {"limit": limit}
    if agent_id is not None:
        params["agent"] = agent_id
    if environment is not None:
        params["env"] = environment
    return params


def diff_request_body(
    *,
    baseline_release_id: str,
    candidate_release_id: str,
    window: str,
    environment: str | None,
    tenant_id: str | None,
    task_id: str | None,
) -> dict[str, Any]:
    return {
        "baseline_release_id": baseline_release_id,
        "candidate_release_id": candidate_release_id,
        "window": window,
        "environment": environment,
        "tenant_id": tenant_id,
        "task_id": task_id,
    }


def promote_like_body(
    *,
    release_id: str,
    environment: str,
    window: str,
    reason: str,
    actor: str,
) -> dict[str, Any]:
    return {
        "release_id": release_id,
        "environment": environment,
        "window": window,
        "reason": reason,
        "actor": actor,
    }


def promote_confirm_body(*, request_id: str, approval_reason: str, actor: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "approval_reason": approval_reason,
        "actor": actor,
    }


def promotion_requests_params(*, status: str | None, limit: int) -> dict[str, str | int]:
    params: dict[str, str | int] = {"limit": limit}
    if status is not None:
        params["status"] = status
    return params


def runs_list_params(
    *,
    release_id: str,
    window: str,
    environment: str | None,
    tenant_id: str | None,
    task_id: str | None,
    trace_id: str | None,
    session_id: str | None,
    span_id: str | None,
    offset: int,
    limit: int,
) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "release_id": release_id,
        "window": window,
        "limit": limit,
        "offset": offset,
    }
    if environment is not None:
        params["environment"] = environment
    if tenant_id is not None:
        params["tenant_id"] = tenant_id
    if task_id is not None:
        params["task_id"] = task_id
    if trace_id is not None:
        params["trace_id"] = trace_id
    if session_id is not None:
        params["session_id"] = session_id
    if span_id is not None:
        params["span_id"] = span_id
    return params


def rollback_body(
    *,
    release_id: str,
    environment: str,
    window: str,
    reason: str,
    actor: str,
) -> dict[str, Any]:
    return {
        "release_id": release_id,
        "environment": environment,
        "window": window,
        "reason": reason,
        "actor": actor,
    }


def events_ingest_json(events: Iterable[RunEvent]) -> dict[str, Any] | None:
    payload = {"events": [e.model_dump(mode="json") for e in events]}
    if not payload["events"]:
        return None
    return payload


EXPORT_HEADER_KEYS = (
    "X-Flightdeck-Matched-Total",
    "X-Flightdeck-Returned",
    "X-Flightdeck-Offset",
    "X-Flightdeck-Truncated",
)


def export_headers_from_response(resp: httpx.Response) -> dict[str, str]:
    return {k: resp.headers[k] for k in EXPORT_HEADER_KEYS if k in resp.headers}


def sync_request_with_retry(
    client: httpx.Client,
    *,
    url: str,
    policy: HttpRetryPolicy,
    method: str,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: httpx.RequestError | None = None
    for attempt in range(policy.max_retries + 1):
        try:
            return client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt >= policy.max_retries:
                raise
            time.sleep(policy.backoff_s * (2**attempt))
    assert last_exc is not None
    raise last_exc


async def async_request_with_retry(
    client: httpx.AsyncClient,
    *,
    url: str,
    policy: HttpRetryPolicy,
    method: str,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: httpx.RequestError | None = None
    for attempt in range(policy.max_retries + 1):
        try:
            return await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt >= policy.max_retries:
                raise
            await asyncio.sleep(policy.backoff_s * (2**attempt))
    assert last_exc is not None
    raise last_exc
