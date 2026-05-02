from __future__ import annotations

import asyncio
import time
from typing import Any, Iterable

import httpx

from flightdeck.models import RunEvent


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
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_s)
        self._max_retries = max(0, max_retries)
        self._retry_backoff_s = max(0.0, retry_backoff_s)
        self._api_token = api_token

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _auth_headers(self) -> dict[str, str]:
        if self._api_token:
            return {"Authorization": f"Bearer {self._api_token}"}
        return {}

    def _json_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", **self._auth_headers()}

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
        params: dict[str, str | int] = {"limit": limit}
        if agent_id is not None:
            params["agent"] = agent_id
        if environment is not None:
            params["env"] = environment
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
        body: dict[str, Any] = {
            "baseline_release_id": baseline_release_id,
            "candidate_release_id": candidate_release_id,
            "window": window,
            "environment": environment,
            "tenant_id": tenant_id,
            "task_id": task_id,
        }
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
        body = {
            "release_id": release_id,
            "environment": environment,
            "window": window,
            "reason": reason,
            "actor": actor,
        }
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
        body = {
            "release_id": release_id,
            "environment": environment,
            "window": window,
            "reason": reason,
            "actor": actor,
        }
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
        body = {
            "request_id": request_id,
            "approval_reason": approval_reason,
            "actor": actor,
        }
        resp = self._request_with_retry("POST", "/v1/promote/confirm", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    def list_promotion_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {"limit": limit}
        if status is not None:
            params["status"] = status
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
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "release_id": release_id,
            "window": window,
            "limit": limit,
        }
        if environment is not None:
            params["environment"] = environment
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
        if task_id is not None:
            params["task_id"] = task_id
        resp = self._request_with_retry(
            "GET",
            "/v1/runs",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    def post_rollback(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = {
            "release_id": release_id,
            "environment": environment,
            "window": window,
            "reason": reason,
            "actor": actor,
        }
        resp = self._request_with_retry("POST", "/v1/rollback", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    def ingest_run_events(self, events: Iterable[RunEvent]) -> int:
        payload = {"events": [e.model_dump(mode="json") for e in events]}
        if not payload["events"]:
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

    def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        last_exc: httpx.RequestError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._client.request(method, f"{self._base_url}{path}", **kwargs)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    raise
                time.sleep(self._retry_backoff_s * (2**attempt))
        assert last_exc is not None
        raise last_exc


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
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._max_retries = max(0, max_retries)
        self._retry_backoff_s = max(0.0, retry_backoff_s)
        self._api_token = api_token

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _auth_headers(self) -> dict[str, str]:
        if self._api_token:
            return {"Authorization": f"Bearer {self._api_token}"}
        return {}

    def _json_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", **self._auth_headers()}

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
        params: dict[str, str | int] = {"limit": limit}
        if agent_id is not None:
            params["agent"] = agent_id
        if environment is not None:
            params["env"] = environment
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
        body: dict[str, Any] = {
            "baseline_release_id": baseline_release_id,
            "candidate_release_id": candidate_release_id,
            "window": window,
            "environment": environment,
            "tenant_id": tenant_id,
            "task_id": task_id,
        }
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
        body = {
            "release_id": release_id,
            "environment": environment,
            "window": window,
            "reason": reason,
            "actor": actor,
        }
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
        body = {
            "release_id": release_id,
            "environment": environment,
            "window": window,
            "reason": reason,
            "actor": actor,
        }
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
        body = {
            "request_id": request_id,
            "approval_reason": approval_reason,
            "actor": actor,
        }
        resp = await self._request_with_retry("POST", "/v1/promote/confirm", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    async def list_promotion_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {"limit": limit}
        if status is not None:
            params["status"] = status
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
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "release_id": release_id,
            "window": window,
            "limit": limit,
        }
        if environment is not None:
            params["environment"] = environment
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
        if task_id is not None:
            params["task_id"] = task_id
        resp = await self._request_with_retry(
            "GET",
            "/v1/runs",
            params=params,
            headers=self._auth_headers() or None,
        )
        resp.raise_for_status()
        return resp.json()

    async def post_rollback(
        self,
        *,
        release_id: str,
        environment: str,
        window: str,
        reason: str,
        actor: str = "sdk",
    ) -> dict[str, Any]:
        body = {
            "release_id": release_id,
            "environment": environment,
            "window": window,
            "reason": reason,
            "actor": actor,
        }
        resp = await self._request_with_retry("POST", "/v1/rollback", json=body, headers=self._json_headers())
        resp.raise_for_status()
        return resp.json()

    async def ingest_run_events(self, events: Iterable[RunEvent]) -> int:
        payload = {"events": [e.model_dump(mode="json") for e in events]}
        if not payload["events"]:
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

    async def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        last_exc: httpx.RequestError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._client.request(method, f"{self._base_url}{path}", **kwargs)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    raise
                await asyncio.sleep(self._retry_backoff_s * (2**attempt))
        assert last_exc is not None
        raise last_exc
