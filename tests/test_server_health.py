from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from flightdeck.cli.main import cli
from flightdeck.server.app import create_app
from flightdeck.storage import LATEST_SCHEMA_MIGRATION_VERSION
from tests.test_spine import write_pricing, write_release


def test_health_includes_mutation_auth_loopback_when_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mutation_auth": "loopback", "read_auth": "open"}


def test_ui_icon_png_served() -> None:
    with TestClient(create_app()) as client:
        r = client.get("/flightdeck-icon.png")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")


def test_health_includes_mutation_auth_bearer_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "test-secret-token")
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mutation_auth": "bearer", "read_auth": "bearer"}


def test_health_whitespace_only_token_treated_as_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "   \t  ")
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["mutation_auth"] == "loopback"
    assert r.json()["read_auth"] == "open"


def test_get_v1_metrics_401_without_bearer_when_token_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "metrics-read-gate")
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/v1/metrics")
    assert r.status_code == 401
    assert "read route" in r.json()["detail"]


def test_get_v1_metrics_200_with_bearer_when_token_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "metrics-read-ok")
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/v1/metrics", headers={"Authorization": "Bearer metrics-read-ok"})
    assert r.status_code == 200
    assert r.json()["counters"]["releases_total"] == 0


def test_v1_metrics_returns_counters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0

    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    rel_dir = write_release(
        tmp_path,
        agent_id="agent_metrics",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    release_id = runner.invoke(cli, ["release", "register", str(rel_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc).isoformat()
    for i in range(2):
        event = {
            "api_version": "v1",
            "type": "run_end",
            "timestamp": now,
            "workspace_id": "ws_local",
            "agent_id": "agent_metrics",
            "release_id": release_id,
            "run_id": f"metrics_run_{i}",
            "tenant_id": "t",
            "task_id": "task",
            "environment": "local",
            "metrics": {"latency_ms": 100, "success": True, "error_type": None},
            "usage": {
                "model": {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cached_input_tokens": 0,
                },
                "tools": [],
            },
            "labels": {},
        }
        p = tmp_path / f"ev_{i}.json"
        p.write_text(json.dumps([event]), encoding="utf-8")
        assert runner.invoke(cli, ["runs", "ingest", str(p)]).exit_code == 0

    with TestClient(create_app()) as client:
        r = client.get("/v1/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == LATEST_SCHEMA_MIGRATION_VERSION
    assert "generated_at" in body
    c = body["counters"]
    assert c["releases_total"] == 1
    assert c["pricing_tables_total"] == 1
    assert c["run_events_total"] == 2
    assert c["promoted_pointers_total"] == 0
    assert c["actions_total"] == 0
    assert c["actions_by_action"] == {}
