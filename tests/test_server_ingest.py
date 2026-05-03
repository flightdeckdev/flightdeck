from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from click.testing import CliRunner
from fastapi.testclient import TestClient

from flightdeck.cli.main import cli
from flightdeck.server.app import create_app


def test_post_v1_events_ingests(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    pricing = {
        "provider": "openai",
        "pricing_version": "openai-2026-04-30",
        "entries": [
            {"model": "gpt-4.1-mini", "input_usd_per_1k_tokens": 1.0, "output_usd_per_1k_tokens": 2.0},
        ],
    }
    pricing_path = tmp_path / "pricing.yaml"
    pricing_path.write_text(yaml.safe_dump(pricing, sort_keys=False), encoding="utf-8")
    assert runner.invoke(cli, ["pricing", "import", str(pricing_path)]).exit_code == 0

    rel_dir = tmp_path / "release"
    rel_dir.mkdir()
    (rel_dir / "prompts").mkdir()
    (rel_dir / "prompts" / "system.md").write_text("system", encoding="utf-8")
    release = {
        "api_version": "v1",
        "kind": "Release",
        "metadata": {"name": "support-agent", "version": "1"},
        "spec": {
            "agent": {"agent_id": "agent_support"},
            "runtime": {"provider": "openai", "model": "gpt-4.1-mini"},
            "prompts": {"system_ref": "prompts/system.md"},
            "pricing_reference": {"provider": "openai", "pricing_version": "openai-2026-04-30"},
        },
    }
    (rel_dir / "release.yaml").write_text(yaml.safe_dump(release, sort_keys=False), encoding="utf-8")
    release_id = runner.invoke(cli, ["release", "register", str(rel_dir)]).output.strip()

    app = create_app()
    client = TestClient(app)

    now = datetime.now(tz=timezone.utc).isoformat()
    event = {
        "api_version": "v1",
        "type": "run_end",
        "timestamp": now,
        "workspace_id": "ws_local",
        "agent_id": "agent_support",
        "release_id": release_id,
        "run_id": "http-ingest-1",
        "tenant_id": "tenant_acme",
        "task_id": "task_support",
        "environment": "local",
        "metrics": {"latency_ms": 1000, "success": True, "error_type": None},
        "usage": {
            "model": {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cached_input_tokens": 0,
            },
            "tools": [],
        },
        "labels": {"test": "server"},
    }

    resp = client.post("/v1/events", json={"events": [event]})
    assert resp.status_code == 200
    assert resp.json() == {"inserted": 1}


def test_post_v1_events_rejects_non_v1_api_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    app = create_app()
    client = TestClient(app)
    now = datetime.now(tz=timezone.utc).isoformat()
    event = {
        "api_version": "v2",
        "type": "run_end",
        "timestamp": now,
        "workspace_id": "ws_local",
        "agent_id": "agent_support",
        "release_id": "rel_x",
        "run_id": "bad-api-1",
        "tenant_id": "tenant_acme",
        "task_id": "task_support",
        "environment": "local",
        "metrics": {"latency_ms": 1000, "success": True, "error_type": None},
        "usage": {
            "model": {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cached_input_tokens": 0,
            },
            "tools": [],
        },
        "labels": {},
    }
    resp = client.post("/v1/events", json={"events": [event]})
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "Unsupported api_version for POST /v1/events: 'v2' (only 'v1' is accepted)."
    )


def _make_run_event_dict(*, api_version: str | None = "v1") -> dict:
    now = datetime.now(tz=timezone.utc).isoformat()
    return {
        "api_version": api_version,
        "type": "run_end",
        "timestamp": now,
        "workspace_id": "ws_local",
        "agent_id": "agent_support",
        "release_id": "rel_x",
        "run_id": "bad-api-edge",
        "tenant_id": "tenant_acme",
        "task_id": "task_support",
        "environment": "local",
        "metrics": {"latency_ms": 1000, "success": True, "error_type": None},
        "usage": {
            "model": {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cached_input_tokens": 0,
            },
            "tools": [],
        },
        "labels": {},
    }


def test_post_v1_events_rejects_empty_api_version_string(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init"]).exit_code == 0
    app = create_app()
    client = TestClient(app)
    ev = _make_run_event_dict(api_version="")
    resp = client.post("/v1/events", json={"events": [ev]})
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "Unsupported api_version for POST /v1/events: '' (only 'v1' is accepted)."
    )


def test_post_v1_events_rejects_wrong_casing_v1(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init"]).exit_code == 0
    app = create_app()
    client = TestClient(app)
    ev = _make_run_event_dict(api_version="V1")
    resp = client.post("/v1/events", json={"events": [ev]})
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "Unsupported api_version for POST /v1/events: 'V1' (only 'v1' is accepted)."
    )


def test_post_v1_events_rejects_null_api_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init"]).exit_code == 0
    app = create_app()
    client = TestClient(app)
    ev = _make_run_event_dict()
    ev["api_version"] = None
    resp = client.post("/v1/events", json={"events": [ev]})
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "Unsupported api_version for POST /v1/events: None (only 'v1' is accepted)."
    )


def test_post_v1_events_accepts_omitted_api_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    pricing = {
        "provider": "openai",
        "pricing_version": "openai-2026-04-30",
        "entries": [
            {"model": "gpt-4.1-mini", "input_usd_per_1k_tokens": 1.0, "output_usd_per_1k_tokens": 2.0},
        ],
    }
    pricing_path = tmp_path / "pricing.yaml"
    pricing_path.write_text(yaml.safe_dump(pricing, sort_keys=False), encoding="utf-8")
    assert runner.invoke(cli, ["pricing", "import", str(pricing_path)]).exit_code == 0

    rel_dir = tmp_path / "release"
    rel_dir.mkdir()
    (rel_dir / "prompts").mkdir()
    (rel_dir / "prompts" / "system.md").write_text("system", encoding="utf-8")
    release = {
        "api_version": "v1",
        "kind": "Release",
        "metadata": {"name": "support-agent", "version": "1"},
        "spec": {
            "agent": {"agent_id": "agent_support"},
            "runtime": {"provider": "openai", "model": "gpt-4.1-mini"},
            "prompts": {"system_ref": "prompts/system.md"},
            "pricing_reference": {"provider": "openai", "pricing_version": "openai-2026-04-30"},
        },
    }
    (rel_dir / "release.yaml").write_text(yaml.safe_dump(release, sort_keys=False), encoding="utf-8")
    release_id = runner.invoke(cli, ["release", "register", str(rel_dir)]).output.strip()

    app = create_app()
    client = TestClient(app)
    now = datetime.now(tz=timezone.utc).isoformat()
    event = {
        "type": "run_end",
        "timestamp": now,
        "workspace_id": "ws_local",
        "agent_id": "agent_support",
        "release_id": release_id,
        "run_id": "http-omit-api-version",
        "tenant_id": "tenant_acme",
        "task_id": "task_support",
        "environment": "local",
        "metrics": {"latency_ms": 1000, "success": True, "error_type": None},
        "usage": {
            "model": {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cached_input_tokens": 0,
            },
            "tools": [],
        },
        "labels": {},
    }

    resp = client.post("/v1/events", json={"events": [event]})
    assert resp.status_code == 200
    assert resp.json() == {"inserted": 1}


def test_post_v1_events_rejects_non_loopback_without_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init"]).exit_code == 0
    app = create_app()
    transport = httpx.ASGITransport(app=app, client=("198.51.100.2", 44444))

    async def _run() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/v1/events", json={"events": [_make_run_event_dict()]})

    resp = asyncio.run(_run())
    assert resp.status_code == 403
    assert "local clients" in resp.json()["detail"]


def test_post_v1_events_non_loopback_requires_bearer_when_token_set(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "ingest-test-secret")
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init"]).exit_code == 0
    app = create_app()
    transport = httpx.ASGITransport(app=app, client=("198.51.100.3", 44444))

    async def _run() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/v1/events", json={"events": [_make_run_event_dict()]})

    resp = asyncio.run(_run())
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing or invalid API token for mutation route."


def test_post_v1_events_accepts_non_loopback_with_bearer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "ingest-bearer-ok")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    pricing = {
        "provider": "openai",
        "pricing_version": "openai-2026-04-30",
        "entries": [
            {"model": "gpt-4.1-mini", "input_usd_per_1k_tokens": 1.0, "output_usd_per_1k_tokens": 2.0},
        ],
    }
    pricing_path = tmp_path / "pricing.yaml"
    pricing_path.write_text(yaml.safe_dump(pricing, sort_keys=False), encoding="utf-8")
    assert runner.invoke(cli, ["pricing", "import", str(pricing_path)]).exit_code == 0

    rel_dir = tmp_path / "release"
    rel_dir.mkdir()
    (rel_dir / "prompts").mkdir()
    (rel_dir / "prompts" / "system.md").write_text("system", encoding="utf-8")
    release = {
        "api_version": "v1",
        "kind": "Release",
        "metadata": {"name": "support-agent", "version": "1"},
        "spec": {
            "agent": {"agent_id": "agent_support"},
            "runtime": {"provider": "openai", "model": "gpt-4.1-mini"},
            "prompts": {"system_ref": "prompts/system.md"},
            "pricing_reference": {"provider": "openai", "pricing_version": "openai-2026-04-30"},
        },
    }
    (rel_dir / "release.yaml").write_text(yaml.safe_dump(release, sort_keys=False), encoding="utf-8")
    release_id = runner.invoke(cli, ["release", "register", str(rel_dir)]).output.strip()

    app = create_app()
    now = datetime.now(tz=timezone.utc).isoformat()
    event = {
        "api_version": "v1",
        "type": "run_end",
        "timestamp": now,
        "workspace_id": "ws_local",
        "agent_id": "agent_support",
        "release_id": release_id,
        "run_id": "remote-ingest-1",
        "tenant_id": "tenant_acme",
        "task_id": "task_support",
        "environment": "local",
        "metrics": {"latency_ms": 1000, "success": True, "error_type": None},
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
        "labels": {"test": "remote-bearer"},
    }
    transport = httpx.ASGITransport(app=app, client=("198.51.100.9", 44444))

    async def _run() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/v1/events",
                json={"events": [event]},
                headers={"Authorization": "Bearer ingest-bearer-ok"},
            )

    resp = asyncio.run(_run())
    assert resp.status_code == 200
    assert resp.json() == {"inserted": 1}
