from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from flightdeck.cli.main import cli
from tests.test_spine import write_events, write_policy, write_pricing, write_release


def test_release_verify_checksum_mismatch_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    rel_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    release_id = runner.invoke(cli, ["release", "register", str(rel_dir)]).output.strip()

    prompt_file = rel_dir / "prompts" / "system.md"
    prompt_file.write_text("system changed", encoding="utf-8")
    res = runner.invoke(cli, ["release", "verify", release_id, "--path", str(rel_dir)])
    assert res.exit_code == 2
    assert "CHECKSUM MISMATCH" in res.output


def test_release_diff_fail_on_policy_exits_1(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(tmp_path, max_cost_per_run_usd=0.000001)
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0

    baseline = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    candidate = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    be = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=3, ts=now)
    ce = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=3, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(be)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(ce)]).exit_code == 0

    res_ok = runner.invoke(
        cli,
        ["release", "diff", baseline_id, candidate_id, "--window", "7d"],
    )
    assert res_ok.exit_code == 0
    assert "Policy: FAIL" in res_ok.output

    res_gate = runner.invoke(
        cli,
        ["release", "diff", baseline_id, candidate_id, "--window", "7d", "--fail-on-policy"],
    )
    assert res_gate.exit_code != 0
    assert "Policy gate: diff blocked by active policy" in res_gate.output


def test_release_diff_contract_invalid_window_is_nonzero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0

    baseline = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    candidate = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate)]).output.strip()
    res = runner.invoke(cli, ["release", "diff", baseline_id, candidate_id, "--window", "7x"])
    assert res.exit_code != 0
    assert "Invalid window unit: 7x" in res.output


def test_release_promote_policy_fail_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(tmp_path, max_cost_per_run_usd=0.0001)
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    baseline = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    candidate = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    be = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=5, ts=now)
    ce = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=5, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(be)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(ce)]).exit_code == 0
    assert (
        runner.invoke(
            cli,
            ["release", "promote", baseline_id, "--env", "local", "--window", "7d", "--reason", "baseline"],
        ).exit_code
        == 0
    )
    res = runner.invoke(
        cli,
        ["release", "promote", candidate_id, "--env", "local", "--window", "7d", "--reason", "attempt"],
    )
    assert res.exit_code != 0
    assert "Policy: FAIL" in res.output
    assert "Promotion blocked by policy" in res.output


def test_release_verify_ok_exits_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    rel_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    release_id = runner.invoke(cli, ["release", "register", str(rel_dir)]).output.strip()
    res = runner.invoke(cli, ["release", "verify", release_id, "--path", str(rel_dir)])
    assert res.exit_code == 0
    assert "OK: checksum matches" in res.output


def test_release_diff_unknown_baseline_nonzero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    cand = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    candidate_id = runner.invoke(cli, ["release", "register", str(cand)]).output.strip()
    res = runner.invoke(cli, ["release", "diff", "rel_does_not_exist", candidate_id, "--window", "7d"])
    assert res.exit_code != 0
    assert "Unknown baseline release" in res.output


def test_release_history_shows_promote_line(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(tmp_path, max_cost_per_run_usd=10.0)
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    baseline = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    candidate = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    be = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=5, ts=now)
    ce = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=5, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(be)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(ce)]).exit_code == 0
    assert (
        runner.invoke(
            cli,
            ["release", "promote", baseline_id, "--env", "local", "--window", "7d", "--reason", "first"],
        ).exit_code
        == 0
    )

    hist = runner.invoke(cli, ["release", "history", "--agent", "agent_support", "--env", "local"])
    assert hist.exit_code == 0
    assert "promote" in hist.output
    assert baseline_id in hist.output


def test_release_rollback_exits_zero_and_history_shows_rollback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(tmp_path, max_cost_per_run_usd=10.0)
    assert runner.invoke(cli, ["policy", "set", str(policy)]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0
    baseline_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    candidate_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    rollback_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="3",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()
    rollback_id = runner.invoke(cli, ["release", "register", str(rollback_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    for rid in (baseline_id, candidate_id, rollback_id):
        ev = write_events(tmp_path, release_id=rid, agent_id="agent_support", n=5, ts=now)
        assert runner.invoke(cli, ["runs", "ingest", str(ev)]).exit_code == 0

    assert (
        runner.invoke(
            cli,
            ["release", "promote", baseline_id, "--env", "local", "--window", "7d", "--reason", "baseline"],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            cli,
            ["release", "promote", candidate_id, "--env", "local", "--window", "7d", "--reason", "candidate"],
        ).exit_code
        == 0
    )
    rb = runner.invoke(
        cli,
        ["release", "rollback", rollback_id, "--env", "local", "--window", "7d", "--reason", "rollback smoke"],
    )
    assert rb.exit_code == 0
    assert "Rolled back" in rb.output

    hist = runner.invoke(cli, ["release", "history", "--agent", "agent_support", "--env", "local"])
    assert hist.exit_code == 0
    assert "rollback" in hist.output
    assert rollback_id in hist.output
