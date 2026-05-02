from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from flightdeck.server.app import create_app


def test_health_includes_mutation_auth_loopback_when_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mutation_auth": "loopback"}


def test_health_includes_mutation_auth_bearer_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "test-secret-token")
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mutation_auth": "bearer"}


def test_health_whitespace_only_token_treated_as_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "   \t  ")
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["mutation_auth"] == "loopback"
