from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml
from click.testing import CliRunner
from fastapi.testclient import TestClient

from flightdeck.cli.main import cli
from flightdeck.server.app import create_app
from tests.test_spine import write_events, write_policy, write_pricing, write_release


@contextmanager
def _cwd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _enable_promotion_approval(path: Path) -> None:
    p = path / "flightdeck.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    data["promotion_requires_approval"] = True
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n")


def test_pricing_hints_when_alternate_pricing_version_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(
        tmp_path,
        min_candidate_runs=0,
        min_baseline_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=False,
    )
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
    p1 = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    p2 = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-05-01")
    assert runner.invoke(cli, ["pricing", "import", str(p1)]).exit_code == 0
    assert runner.invoke(cli, ["pricing", "import", str(p2)]).exit_code == 0
    r1 = write_release(tmp_path, agent_id="a", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    r2 = write_release(tmp_path, agent_id="a", version="2", pricing_provider="openai", pricing_version="openai-2026-04-30")
    rel1 = runner.invoke(cli, ["release", "register", str(r1)]).output.strip()
    rel2 = runner.invoke(cli, ["release", "register", str(r2)]).output.strip()
    res = runner.invoke(cli, ["release", "diff", rel1, rel2, "--window", "7d", "--output", "json"])
    assert res.exit_code == 0
    body = json.loads(res.output)
    hints = body["pricing"]["hints"]
    assert hints
    assert any("other imported pricing_version" in h for h in hints)


def test_catalog_comparable_cost_on_cross_provider_diff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(
        tmp_path,
        min_candidate_runs=0,
        min_baseline_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=False,
    )
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0

    openai_p = write_pricing(
        tmp_path,
        provider="openai",
        pricing_version="openai-2026-04-30",
        model="gpt-4o-mini",
        input_price=1.0,
        output_price=2.0,
    )
    anthropic_p = write_pricing(
        tmp_path,
        provider="anthropic",
        pricing_version="anthropic-2026-04-30",
        model="claude-3-5-sonnet-20241022",
        input_price=3.0,
        output_price=4.0,
    )
    assert runner.invoke(cli, ["pricing", "import", str(openai_p)]).exit_code == 0
    assert runner.invoke(cli, ["pricing", "import", str(anthropic_p)]).exit_code == 0

    cat = {
        "api_version": "v1",
        "kind": "PricingCatalog",
        "catalog_version": "test-1",
        "mappings": [
            {
                "provider": "openai",
                "pricing_version": "openai-2026-04-30",
                "model": "gpt-4o-mini",
                "catalog_slot_id": "slot_a",
            },
            {
                "provider": "anthropic",
                "pricing_version": "anthropic-2026-04-30",
                "model": "claude-3-5-sonnet-20241022",
                "catalog_slot_id": "slot_a",
            },
        ],
        "tariffs": {"slot_a": {"input_usd_per_1k_tokens": 0.5, "output_usd_per_1k_tokens": 1.5}},
    }
    cat_path = tmp_path / "catalog.yaml"
    cat_path.write_text(yaml.safe_dump(cat, sort_keys=False), encoding="utf-8", newline="\n")

    fd = tmp_path / "flightdeck.yaml"
    cfg = yaml.safe_load(fd.read_text(encoding="utf-8")) or {}
    cfg["pricing_catalog_path"] = str(cat_path.name)
    fd.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8", newline="\n")

    b_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
        model="gpt-4o-mini",
    )
    c_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="anthropic",
        pricing_version="anthropic-2026-04-30",
        model="claude-3-5-sonnet-20241022",
    )
    rel_b = runner.invoke(cli, ["release", "register", str(b_dir)]).output.strip()
    rel_c = runner.invoke(cli, ["release", "register", str(c_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    be = write_events(tmp_path, release_id=rel_b, agent_id="agent_support", n=2, ts=now, model="gpt-4o-mini")
    ce = write_events(
        tmp_path,
        release_id=rel_c,
        agent_id="agent_support",
        n=2,
        ts=now,
        model="claude-3-5-sonnet-20241022",
    )
    assert runner.invoke(cli, ["runs", "ingest", str(be)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(ce)]).exit_code == 0

    res = runner.invoke(
        cli,
        ["release", "diff", rel_b, rel_c, "--window", "7d", "--output", "json"],
    )
    assert res.exit_code == 0
    body = json.loads(res.output)
    cat_block = body["pricing"]["catalog"]
    assert cat_block["enabled"] is True
    assert cat_block["catalog_version"] == "test-1"
    assert cat_block["baseline_slot_id"] == "slot_a"
    assert cat_block["candidate_slot_id"] == "slot_a"
    assert cat_block["baseline_cost_per_run_usd"] is not None
    assert cat_block["candidate_cost_per_run_usd"] is not None
    assert cat_block["delta_cost_per_run_usd"] is not None


def test_promotion_request_and_confirm(tmp_path: Path) -> None:
    ws = tmp_path / "apr"
    ws.mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    with _cwd(ws):
        assert runner.invoke(cli, ["init"]).exit_code == 0
        policy = write_policy(ws, min_candidate_runs=0, min_baseline_runs=0, min_low_runs=0)
        assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
        pricing = write_pricing(ws, provider="openai", pricing_version="openai-2026-04-30")
        assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
        b_dir = write_release(ws, agent_id="ag", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
        c_dir = write_release(ws, agent_id="ag", version="2", pricing_provider="openai", pricing_version="openai-2026-04-30")
        bid = runner.invoke(cli, ["release", "register", str(b_dir)]).output.strip()
        cid = runner.invoke(cli, ["release", "register", str(c_dir)]).output.strip()
        now = datetime.now(tz=timezone.utc)
        assert runner.invoke(cli, ["runs", "ingest", str(write_events(ws, release_id=bid, agent_id="ag", n=1, ts=now))]).exit_code == 0
        assert runner.invoke(cli, ["runs", "ingest", str(write_events(ws, release_id=cid, agent_id="ag", n=1, ts=now))]).exit_code == 0
        assert (
            runner.invoke(cli, ["release", "promote", bid, "--env", "local", "--window", "7d", "--reason", "seed"]).exit_code
            == 0
        )
        _enable_promotion_approval(ws)
        assert (
            runner.invoke(cli, ["release", "promote", cid, "--env", "local", "--window", "7d", "--reason", "direct"]).exit_code
            != 0
        )
        rq = runner.invoke(
            cli,
            ["release", "promote-request", cid, "--env", "local", "--window", "7d", "--reason", "please"],
        )
        assert rq.exit_code == 0
        req_id = [ln for ln in rq.output.splitlines() if ln.startswith("request_id=")][0].split("=", 1)[1]
        cf = runner.invoke(
            cli,
            ["release", "promote-confirm", req_id, "--approval-reason", "lgtm"],
        )
        assert cf.exit_code == 0


def test_get_v1_runs(tmp_path: Path) -> None:
    ws = tmp_path / "runs_http"
    ws.mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    with _cwd(ws):
        assert runner.invoke(cli, ["init"]).exit_code == 0
        policy = write_policy(ws, min_candidate_runs=0, min_baseline_runs=0, min_low_runs=0)
        assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
        pricing = write_pricing(ws, provider="openai", pricing_version="openai-2026-04-30")
        assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
        rdir = write_release(ws, agent_id="ag", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
        rid = runner.invoke(cli, ["release", "register", str(rdir)]).output.strip()
        now = datetime.now(tz=timezone.utc)
        ev = write_events(ws, release_id=rid, agent_id="ag", n=3, ts=now)
        assert runner.invoke(cli, ["runs", "ingest", str(ev)]).exit_code == 0

    with _cwd(ws):
        with TestClient(create_app()) as client:
            resp = client.get("/v1/runs", params={"release_id": rid, "window": "7d", "limit": 10})
            assert resp.status_code == 200
            data = resp.json()
            assert data["matched_total"] == 3
            assert data["returned"] == 3
            assert len(data["events"]) == 3


def test_cli_runs_list_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(tmp_path, min_candidate_runs=0, min_baseline_runs=0, min_low_runs=0)
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    rdir = write_release(tmp_path, agent_id="ag", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    rid = runner.invoke(cli, ["release", "register", str(rdir)]).output.strip()
    now = datetime.now(tz=timezone.utc)
    assert runner.invoke(cli, ["runs", "ingest", str(write_events(tmp_path, release_id=rid, agent_id="ag", n=1, ts=now))]).exit_code == 0
    res = runner.invoke(cli, ["runs", "list", rid, "--window", "7d", "--output", "json"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["matched_total"] == 1


def test_diff_survives_malformed_catalog_yaml_syntax(tmp_path: Path, monkeypatch) -> None:
    """Invalid YAML in pricing catalog must not crash diff (YAMLError → catalog warning)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    (tmp_path / "bad_catalog.yaml").write_text("catalog_version: 'unterminated\n", encoding="utf-8")
    fd = tmp_path / "flightdeck.yaml"
    cfg = yaml.safe_load(fd.read_text(encoding="utf-8")) or {}
    cfg["pricing_catalog_path"] = "bad_catalog.yaml"
    fd.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8", newline="\n")

    policy = write_policy(
        tmp_path,
        min_candidate_runs=0,
        min_baseline_runs=0,
        min_low_runs=0,
        require_high_diff_confidence=False,
    )
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    r1 = write_release(tmp_path, agent_id="a", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    r2 = write_release(tmp_path, agent_id="a", version="2", pricing_provider="openai", pricing_version="openai-2026-04-30")
    rel1 = runner.invoke(cli, ["release", "register", str(r1)]).output.strip()
    rel2 = runner.invoke(cli, ["release", "register", str(r2)]).output.strip()

    res = runner.invoke(cli, ["release", "diff", rel1, rel2, "--window", "7d", "--output", "json"])
    assert res.exit_code == 0
    body = json.loads(res.output)
    assert body["policy"]["passed"] is True
    w = body["pricing"]["catalog"]["warnings"]
    assert w
    assert any("YAML parse error" in x for x in w)
    assert body["pricing"]["catalog"]["enabled"] is False
