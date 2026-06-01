from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from flightdeck.cli.main import cli
from flightdeck.server.app import create_app
from flightdeck.storage import LATEST_SCHEMA_MIGRATION_VERSION


def test_prometheus_metrics_200_no_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /metrics returns 200 with no token set (open read access)."""
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics")
    assert r.status_code == 200


def test_prometheus_metrics_content_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /metrics content-type contains 'text/plain'."""
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/plain; version=0.0.4")


def test_prometheus_metrics_contains_releases_total(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Response body contains flightdeck_releases_total."""
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics")
    assert "flightdeck_releases_total" in r.text


def test_prometheus_metrics_contains_schema_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Response body contains flightdeck_schema_version."""
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics")
    assert "flightdeck_schema_version" in r.text


def test_prometheus_metrics_values_are_parseable_floats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All metric value tokens in the response are parseable as floats (Prometheus requirement)."""
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    for line in r.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Last token on a metric line is the value
        value_token = line.rsplit(" ", 1)[-1]
        float(value_token)  # raises ValueError if not parseable


def test_prometheus_metrics_schema_version_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """flightdeck_schema_version value matches LATEST_SCHEMA_MIGRATION_VERSION."""
    monkeypatch.delenv("FLIGHTDECK_LOCAL_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    for line in r.text.splitlines():
        if line.startswith("flightdeck_schema_version "):
            value = float(line.split()[-1])
            assert value == float(LATEST_SCHEMA_MIGRATION_VERSION)
            break
    else:
        pytest.fail("flightdeck_schema_version metric line not found")


def test_prometheus_metrics_401_without_bearer_when_token_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /metrics returns 401 when token is set and no Bearer is provided."""
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "prom-read-gate")
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics")
    assert r.status_code == 401
    assert "read route" in r.json()["detail"]


def test_prometheus_metrics_200_with_bearer_when_token_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /metrics returns 200 when correct Bearer token is provided."""
    monkeypatch.setenv("FLIGHTDECK_LOCAL_API_TOKEN", "prom-read-ok")
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    with TestClient(create_app()) as client:
        r = client.get("/metrics", headers={"Authorization": "Bearer prom-read-ok"})
    assert r.status_code == 200
    assert "flightdeck_releases_total" in r.text
