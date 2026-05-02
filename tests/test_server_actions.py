from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner
from fastapi.testclient import TestClient

from flightdeck.cli.main import cli
from flightdeck.config import load_config
from flightdeck.server.app import create_app
from flightdeck.storage import Storage
from tests.test_spine import write_events, write_policy, write_pricing, write_release


@contextmanager
def _cwd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _seed_workspace(path: Path) -> tuple[CliRunner, str, str]:
    path.mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    with _cwd(path):
        assert runner.invoke(cli, ["init"]).exit_code == 0
        policy = write_policy(path, max_cost_per_run_usd=10.0)
        assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
        pricing = write_pricing(path, provider="openai", pricing_version="openai-2026-04-30")
        assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
        baseline_dir = write_release(
            path,
            agent_id="agent_support",
            version="1",
            pricing_provider="openai",
            pricing_version="openai-2026-04-30",
        )
        candidate_dir = write_release(
            path,
            agent_id="agent_support",
            version="2",
            pricing_provider="openai",
            pricing_version="openai-2026-04-30",
        )
        baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
        candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

        now = datetime.now(tz=timezone.utc)
        baseline_events = write_events(path, release_id=baseline_id, agent_id="agent_support", n=5, ts=now)
        candidate_events = write_events(path, release_id=candidate_id, agent_id="agent_support", n=5, ts=now)
        assert runner.invoke(cli, ["runs", "ingest", str(baseline_events)]).exit_code == 0
        assert runner.invoke(cli, ["runs", "ingest", str(candidate_events)]).exit_code == 0
        assert (
            runner.invoke(
                cli,
                ["release", "promote", baseline_id, "--env", "local", "--window", "7d", "--reason", "baseline"],
            ).exit_code
            == 0
        )
    return runner, baseline_id, candidate_id


def test_http_routes_expose_read_and_diff(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner, baseline_id, candidate_id = _seed_workspace(ws)
    del runner
    with _cwd(ws):
        with TestClient(create_app()) as client:
            rel = client.get("/v1/releases")
            assert rel.status_code == 200
            assert any(item["release_id"] == baseline_id for item in rel.json()["releases"])

            promoted = client.get("/v1/promoted")
            assert promoted.status_code == 200
            assert promoted.json()["promoted"][0]["release_id"] == baseline_id

            diff_resp = client.post(
                "/v1/diff",
                json={
                    "baseline_release_id": baseline_id,
                    "candidate_release_id": candidate_id,
                    "window": "7d",
                    "environment": "local",
                },
            )
            assert diff_resp.status_code == 200
            body = diff_resp.json()
            assert body["samples"]["baseline_runs"] == 5
            assert body["samples"]["candidate_runs"] == 5


def test_http_promote_parity_with_cli_outcome(tmp_path: Path) -> None:
    cli_ws = tmp_path / "cli"
    http_ws = tmp_path / "http"

    cli_runner, _, cli_candidate_id = _seed_workspace(cli_ws)
    http_runner, _, http_candidate_id = _seed_workspace(http_ws)
    del http_runner

    with _cwd(cli_ws):
        cli_res = cli_runner.invoke(
            cli,
            ["release", "promote", cli_candidate_id, "--env", "local", "--window", "7d", "--reason", "ship"],
        )
        assert cli_res.exit_code == 0
        cli_storage = Storage(load_config().db_path)
        cli_storage.migrate()
        cli_ptr = cli_storage.get_promoted_release_id("agent_support", "local")
        cli_last = cli_storage.list_release_actions(agent_id="agent_support", environment="local")[0]

    with _cwd(http_ws):
        with TestClient(create_app()) as client:
            http_res = client.post(
                "/v1/promote",
                json={
                    "release_id": http_candidate_id,
                    "environment": "local",
                    "window": "7d",
                    "reason": "ship",
                    "actor": "http-test",
                },
            )
            assert http_res.status_code == 200
            assert http_res.json()["promoted_pointer_changed"] is True

        http_storage = Storage(load_config().db_path)
        http_storage.migrate()
        http_ptr = http_storage.get_promoted_release_id("agent_support", "local")
        http_last = http_storage.list_release_actions(agent_id="agent_support", environment="local")[0]

    assert cli_ptr == cli_candidate_id
    assert http_ptr == http_candidate_id
    assert cli_last.action == http_last.action == "promote"
    assert cli_last.policy_result.passed is True
    assert http_last.policy_result.passed is True
    assert cli_last.baseline_release_id is not None
    assert http_last.baseline_release_id is not None


def test_http_promote_requires_reason(tmp_path: Path) -> None:
    ws = tmp_path / "ws_reason"
    _, _, candidate_id = _seed_workspace(ws)
    with _cwd(ws):
        with TestClient(create_app()) as client:
            res = client.post(
                "/v1/promote",
                json={
                    "release_id": candidate_id,
                    "environment": "local",
                    "window": "7d",
                    "reason": "",
                },
            )
    assert res.status_code == 422


def test_ui_root_serves_vite_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(cli, ["init"]).exit_code == 0
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in (r.headers.get("content-type") or "")
    assert '<div id="root"></div>' in r.text
    assert "/assets/" in r.text
