from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from click.testing import CliRunner
from fastapi.testclient import TestClient

from flightdeck.cli.main import cli
from flightdeck.server.app import create_app


@contextmanager
def _cwd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _init_workspace(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    with _cwd(path):
        assert runner.invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0


def test_create_then_list_redacts_secret(tmp_path: Path) -> None:
    _init_workspace(tmp_path)
    with _cwd(tmp_path):
        with TestClient(create_app()) as client:
            r = client.post(
                "/v1/webhooks",
                json={
                    "url": "https://hooks.example.com/foo",
                    "events": ["promote.succeeded"],
                    "description": "prod alerts",
                },
            )
            assert r.status_code == 200, r.text
            created = r.json()
            assert created["kind"] == "Webhook"
            assert created["webhook_id"].startswith("wh_")
            assert created["url"] == "https://hooks.example.com/foo"
            assert created["events"] == ["promote.succeeded"]
            assert created["enabled"] is True
            assert isinstance(created["secret"], str) and len(created["secret"]) >= 40
            assert created["secret_preview"] is None
            full_secret = created["secret"]

            r2 = client.get("/v1/webhooks")
            assert r2.status_code == 200
            body = r2.json()
            assert body["kind"] == "WebhookList"
            assert body["total"] == 1
            item = body["webhooks"][0]
            assert item["webhook_id"] == created["webhook_id"]
            assert item["secret"] is None
            assert item["secret_preview"] is not None
            assert full_secret not in (item["secret_preview"] or "")
            # Preview keeps a hint of the secret without leaking it.
            assert item["secret_preview"].endswith(full_secret[-4:])


def test_unknown_event_is_rejected(tmp_path: Path) -> None:
    _init_workspace(tmp_path)
    with _cwd(tmp_path):
        with TestClient(create_app()) as client:
            r = client.post(
                "/v1/webhooks",
                json={"url": "https://x.example.com", "events": ["bogus.event"]},
            )
    assert r.status_code == 422


def test_delete_webhook(tmp_path: Path) -> None:
    _init_workspace(tmp_path)
    with _cwd(tmp_path):
        with TestClient(create_app()) as client:
            r = client.post(
                "/v1/webhooks",
                json={"url": "https://hooks.example.com/foo", "events": ["rollback.succeeded"]},
            )
            assert r.status_code == 200
            wid = r.json()["webhook_id"]

            d1 = client.delete(f"/v1/webhooks/{wid}")
            assert d1.status_code == 200
            assert d1.json() == {"webhook_id": wid, "deleted": True}

            d2 = client.delete(f"/v1/webhooks/{wid}")
            assert d2.status_code == 404


def test_bearer_required_when_token_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "topsecret-token")
    _init_workspace(tmp_path)
    with _cwd(tmp_path):
        with TestClient(create_app()) as client:
            # Without Bearer: 401.
            r = client.post(
                "/v1/webhooks",
                json={"url": "https://x.example.com", "events": ["promote.succeeded"]},
            )
            assert r.status_code == 401

            # With Bearer: 200.
            r2 = client.post(
                "/v1/webhooks",
                json={"url": "https://x.example.com", "events": ["promote.succeeded"]},
                headers={"Authorization": "Bearer topsecret-token"},
            )
            assert r2.status_code == 200

            # GET also requires Bearer.
            r3 = client.get("/v1/webhooks")
            assert r3.status_code == 401
            r4 = client.get("/v1/webhooks", headers={"Authorization": "Bearer topsecret-token"})
            assert r4.status_code == 200
            assert r4.json()["total"] >= 1
