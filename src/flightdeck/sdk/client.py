from __future__ import annotations

from typing import Iterable

import httpx

from flightdeck.models import RunEvent


class FlightdeckClient:
    def __init__(self, base_url: str, *, timeout_s: float = 5.0, client: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_s)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def ingest_run_events(self, events: Iterable[RunEvent]) -> int:
        payload = {"events": [e.model_dump(mode="json") for e in events]}
        resp = self._client.post(f"{self._base_url}/v1/events", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return int(data["inserted"])
