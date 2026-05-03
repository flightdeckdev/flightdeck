from __future__ import annotations

from typing import Any, Iterable

import httpx

from flightdeck.models import RunEvent
from flightdeck.sdk.http_common import (
    ClientHttpCore,
    HttpRetryPolicy,
    actions_params,
    async_request_with_retry,
    diff_request_body,
    events_ingest_json,
    export_headers_from_response,
    promote_confirm_body,
    promote_like_body,
    promotion_requests_params,
    rollback_body,
    runs_list_params,
    sync_request_with_retry,
)


class FlightdeckClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 5.0,
        max_retries: int = 0,
        retry_backoff_s: float = 0.1,
        api_token: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._core = ClientHttpCore(base_url, api_token)
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_s)
        self._retry = HttpRetryPolicy(max(0, max_retries), max(0.0, retry_backoff_s))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _auth_headers(self) -> dict[str, str]:
        return self._core.auth_headers()

    def _json_headers(self) -> dict[str, str]:
        return self._core.json_headers()

    def _request_with_retry(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return sync_request_with_retry(
            self._client,
            url=self._core.abs_url(path),
            policy=self._retry,
            method=method,
            **kwargs,
        )

    def health(self) -> dict[str, Any]:
        resp = self._request_with_retry("GET", "/health", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    def get_workspace(self) -> dict[str, Any]:
        resp = self._request_with_retry("GET", "/v1/workspace", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    def list_releases(self) -> dict[str, Any]:
        resp = self._request_with_retry("GET", "/v1/releases", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    def list_promoted(self) -> dict[str, Any]:
        resp = self._request_with_retry("GET", "/v1/promoted", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    def list_actions(
        self,
        *,
        agent_id: str | None = None,
        environment: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params = actions_params(agent_id=agent_id, environment=environment, limit=limit)
        resp = self._request_with_retry(
            "GET",
            "/v1/actions",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    def post_diff(
        self,
        *,
        baseline_release_id: str,
        candidate_release_id: str,
        window: str,
        environment: str | None = None,
        tenant_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        body = diff_request_body(
            baseline_release_id=baseline_release_id,
            candidate_release_id=candidate_release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
        )
        resp = self._request_with_retry("POST", "/v1/diff", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    def post_promote(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = promote_like_body(
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor,
        )
        resp = self._request_with_retry("POST", "/v1/promote", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    def post_promote_request(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = promote_like_body(
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor,
        )
        resp = self._request_with_retry("POST", "/v1/promote/request", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    def post_promote_confirm(
        self,
        *,
        request_id: str,
        approval_reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = promote_confirm_body(request_id=request_id, approval_reason=approval_reason, actor=actor)
        resp = self._request_with_retry("POST", "/v1/promote/confirm", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    def list_promotion_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params = promotion_requests_params(status=status, limit=limit)
        resp = self._request_with_retry(
            "GET",
            "/v1/promotion-requests",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    def list_runs(
        self,
        *,
        release_id: str,
        window: str,
        environment: str | None = None,
        tenant_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        params = runs_list_params(
            release_id=release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
            trace_id=trace_id,
            session_id=session_id,
            span_id=span_id,
            offset=offset,
            limit=limit,
        )
        resp = self._request_with_retry(
            "GET",
            "/v1/runs",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_runs_export_ndjson(
        self,
        *,
        release_id: str,
        window: str,
        environment: str | None = None,
        tenant_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        offset: int = 0,
        limit: int = 500,
    ) -> tuple[bytes, dict[str, str]]:
        """GET /v1/runs/export — returns raw NDJSON body and selected response headers."""
        params = runs_list_params(
            release_id=release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
            trace_id=trace_id,
            session_id=session_id,
            span_id=span_id,
            offset=offset,
            limit=limit,
        )
        resp = self._request_with_retry(
            "GET",
            "/v1/runs/export",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return (resp.content, export_headers_from_response(resp))

    def post_rollback(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = rollback_body(
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor,
        )
        resp = self._request_with_retry("POST", "/v1/rollback", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    def ingest_run_events(self, events: Iterable[RunEvent]) -> int:
        payload = events_ingest_json(events)
        if payload is None:
            return 0
        resp = self._request_with_retry("POST", "/v1/events", json=payload, headers=self._json_headers())
        resp.raise_for_status()
        data = resp.json()
        return int(data["inserted"])

    def ingest_run_events_batch(self, events: Iterable[RunEvent], *, chunk_size: int = 500) -> int:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        total = 0
        chunk: list[RunEvent] = []
        for event in events:
            chunk.append(event)
            if len(chunk) >= chunk_size:
                total += self.ingest_run_events(chunk)
                chunk = []
        if chunk:
            total += self.ingest_run_events(chunk)
        return total


class AsyncFlightdeckClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 5.0,
        max_retries: int = 0,
        retry_backoff_s: float = 0.1,
        api_token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._core = ClientHttpCore(base_url, api_token)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._retry = HttpRetryPolicy(max(0, max_retries), max(0.0, retry_backoff_s))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _auth_headers(self) -> dict[str, str]:
        return self._core.auth_headers()

    def _json_headers(self) -> dict[str, str]:
        return self._core.json_headers()

    async def _request_with_retry(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return await async_request_with_retry(
            self._client,
            url=self._core.abs_url(path),
            policy=self._retry,
            method=method,
            **kwargs,
        )

    async def health(self) -> dict[str, Any]:
        resp = await self._request_with_retry("GET", "/health", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    async def get_workspace(self) -> dict[str, Any]:
        resp = await self._request_with_retry("GET", "/v1/workspace", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    async def list_releases(self) -> dict[str, Any]:
        resp = await self._request_with_retry("GET", "/v1/releases", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    async def list_promoted(self) -> dict[str, Any]:
        resp = await self._request_with_retry("GET", "/v1/promoted", headers=self._auth_headers() or None)
        resp.raise_for_status()
        return resp.json()

    async def list_actions(
        self,
        *,
        agent_id: str | None = None,
        environment: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params = actions_params(agent_id=agent_id, environment=environment, limit=limit)
        resp = await self._request_with_retry(
            "GET",
            "/v1/actions",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    async def post_diff(
        self,
        *,
        baseline_release_id: str,
        candidate_release_id: str,
        window: str,
        environment: str | None = None,
        tenant_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        body = diff_request_body(
            baseline_release_id=baseline_release_id,
            candidate_release_id=candidate_release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
        )
        resp = await self._request_with_retry("POST", "/v1/diff", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    async def post_promote(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = promote_like_body(
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor,
        )
        resp = await self._request_with_retry("POST", "/v1/promote", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    async def post_promote_request(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = promote_like_body(
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor,
        )
        resp = await self._request_with_retry("POST", "/v1/promote/request", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    async def post_promote_confirm(
        self,
        *,
        request_id: str,
        approval_reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = promote_confirm_body(request_id=request_id, approval_reason=approval_reason, actor=actor)
        resp = await self._request_with_retry("POST", "/v1/promote/confirm", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    async def list_promotion_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params = promotion_requests_params(status=status, limit=limit)
        resp = await self._request_with_retry(
            "GET",
            "/v1/promotion-requests",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    async def list_runs(
        self,
        *,
        release_id: str,
        window: str,
        environment: str | None = None,
        tenant_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        params = runs_list_params(
            release_id=release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
            trace_id=trace_id,
            session_id=session_id,
            span_id=span_id,
            offset=offset,
            limit=limit,
        )
        resp = await self._request_with_retry(
            "GET",
            "/v1/runs",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    async def fetch_runs_export_ndjson(
        self,
        *,
        release_id: str,
        window: str,
        environment: str | None = None,
        tenant_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        offset: int = 0,
        limit: int = 500,
    ) -> tuple[bytes, dict[str, str]]:
        params = runs_list_params(
            release_id=release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
            trace_id=trace_id,
            session_id=session_id,
            span_id=span_id,
            offset=offset,
            limit=limit,
        )
        resp = await self._request_with_retry(
            "GET",
            "/v1/runs/export",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return (resp.content, export_headers_from_response(resp))

    async def post_rollback(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = rollback_body(
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor,
        )
        resp = await self._request_with_retry("POST", "/v1/rollback", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    async def ingest_run_events(self, events: Iterable[RunEvent]) -> int:
        payload = events_ingest_json(events)
        if payload is None:
            return 0
        resp = await self._request_with_retry("POST", "/v1/events", json=payload, headers=self._json_headers())
        resp.raise_for_status()
        data = resp.json()
        return int(data["inserted"])

    async def ingest_run_events_batch(self, events: Iterable[RunEvent], *, chunk_size: int = 500) -> int:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        total = 0
        chunk: list[RunEvent] = []
        for event in events:
            chunk.append(event)
            if len(chunk) >= chunk_size:
                total += await self.ingest_run_events(chunk)
                chunk = []
        if chunk:
            total += await self.ingest_run_events(chunk)
        return total
