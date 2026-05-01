from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from click.testing import CliRunner

from flightdeck.config import load_config
from flightdeck.cli.main import bundle_checksum, cli
from flightdeck.ledger import confidence_label
from flightdeck.storage import Storage


def write_release(
    tmp_path: Path,
    *,
    agent_id: str,
    version: str,
    pricing_provider: str,
    pricing_version: str,
    model: str = "gpt-4.1-mini",
) -> Path:
    rel_dir = tmp_path / f"release_{version}"
    rel_dir.mkdir()
    (rel_dir / "prompts").mkdir()
    (rel_dir / "prompts" / "system.md").write_text("system", encoding="utf-8")
    release = {
        "api_version": "v1",
        "kind": "Release",
        "metadata": {"name": "support-agent", "version": version},
        "spec": {
            "agent": {"agent_id": agent_id},
            "runtime": {"provider": pricing_provider, "model": model},
            "prompts": {"system_ref": "prompts/system.md"},
            "pricing_reference": {"provider": pricing_provider, "pricing_version": pricing_version},
        },
    }
    (rel_dir / "release.yaml").write_text(yaml.safe_dump(release, sort_keys=False), encoding="utf-8")
    return rel_dir


def write_pricing(
    tmp_path: Path,
    *,
    provider: str,
    pricing_version: str,
    model: str = "gpt-4.1-mini",
    input_price: float = 1.0,
    output_price: float = 2.0,
) -> Path:
    p = tmp_path / f"pricing_{provider}_{pricing_version}.yaml"
    data = {
        "provider": provider,
        "pricing_version": pricing_version,
        "entries": [
            {
                "model": model,
                "input_usd_per_1k_tokens": input_price,
                "output_usd_per_1k_tokens": output_price,
            }
        ],
    }
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p


def write_events(
    tmp_path: Path,
    *,
    release_id: str,
    agent_id: str,
    n: int,
    ts: datetime,
    model: str = "gpt-4.1-mini",
) -> Path:
    p = tmp_path / f"events_{release_id}.jsonl"
    lines = []
    for i in range(n):
        e = {
            "api_version": "v1",
            "type": "run_end",
            "timestamp": ts.isoformat(),
            "workspace_id": "ws_local",
            "agent_id": agent_id,
            "release_id": release_id,
            "run_id": f"{release_id}_{i}",
            "tenant_id": "unknown",
            "task_id": "unknown",
            "environment": "local",
            "metrics": {"latency_ms": 1000, "success": True, "error_type": None},
            "usage": {
                "model": {
                    "provider": "openai",
                    "model": model,
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cached_input_tokens": 0,
                },
                "tools": [],
            },
            "labels": {},
        }
        lines.append(json.dumps(e))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_policy(
    tmp_path: Path,
    *,
    max_cost_per_run_usd: float | None = None,
    require_high_diff_confidence: bool = False,
) -> Path:
    p = tmp_path / "policy.yaml"
    data: dict[str, object] = {"policy_id": "test-policy", "require_high_diff_confidence": require_high_diff_confidence}
    if max_cost_per_run_usd is not None:
        data["max_cost_per_run_usd"] = max_cost_per_run_usd
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p


def test_bundle_checksum_stable(tmp_path: Path) -> None:
    rel = write_release(tmp_path, agent_id="agent_support", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    c1 = bundle_checksum(rel)
    c2 = bundle_checksum(rel)
    assert c1 == c2


def test_bundle_checksum_order_independent(tmp_path: Path) -> None:
    rel_dir = tmp_path / "bundle"
    rel_dir.mkdir()
    (rel_dir / "prompts").mkdir()
    (rel_dir / "prompts" / "b.md").write_text("b", encoding="utf-8")
    (rel_dir / "prompts" / "a.md").write_text("a", encoding="utf-8")
    release = {
        "api_version": "v1",
        "kind": "Release",
        "metadata": {"name": "support-agent", "version": "1"},
        "spec": {
            "agent": {"agent_id": "agent_support"},
            "runtime": {"provider": "openai", "model": "gpt-4.1-mini"},
            "prompts": {"system_ref": "prompts/a.md"},
            "pricing_reference": {"provider": "openai", "pricing_version": "openai-2026-04-30"},
        },
    }
    (rel_dir / "release.yaml").write_text(yaml.safe_dump(release, sort_keys=False), encoding="utf-8")

    assert bundle_checksum(rel_dir) == bundle_checksum(rel_dir)


def test_release_diff_invalid_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0

    r1_dir = write_release(tmp_path, agent_id="agent_support", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    r2_dir = write_release(tmp_path, agent_id="agent_support", version="2", pricing_provider="openai", pricing_version="openai-2026-04-30")
    rel1 = runner.invoke(cli, ["release", "register", str(r1_dir)]).output.strip()
    rel2 = runner.invoke(cli, ["release", "register", str(r2_dir)]).output.strip()

    res = runner.invoke(cli, ["release", "diff", rel1, rel2, "--window", "not-a-window"])
    assert res.exit_code != 0
    assert "Invalid window" in res.output


def test_pricing_replace_requires_reason(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0

    res = runner.invoke(cli, ["pricing", "import", "--replace", str(pricing)])
    assert res.exit_code != 0
    assert "--reason is required" in res.output

    res = runner.invoke(cli, ["pricing", "import", "--replace", "--reason", "fix typo", str(pricing)])
    assert res.exit_code == 0


def test_rollback_promotes_prior_release(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    assert runner.invoke(cli, ["init"]).exit_code == 0
    assert runner.invoke(cli, ["policy", "set", str(write_policy(tmp_path))]).exit_code == 0

    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0

    baseline_dir = write_release(tmp_path, agent_id="agent_support", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    candidate_dir = write_release(tmp_path, agent_id="agent_support", version="2", pricing_provider="openai", pricing_version="openai-2026-04-30")
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    baseline_events = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=5, ts=now)
    candidate_events = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=5, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(baseline_events)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(candidate_events)]).exit_code == 0

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
            ["release", "promote", candidate_id, "--env", "local", "--window", "7d", "--reason", "roll forward"],
        ).exit_code
        == 0
    )

    storage = Storage(load_config().db_path)
    storage.migrate()
    assert storage.get_promoted_release_id("agent_support", "local") == candidate_id

    assert (
        runner.invoke(
            cli,
            [
                "release",
                "rollback",
                baseline_id,
                "--env",
                "local",
                "--window",
                "7d",
                "--reason",
                "revert regression",
            ],
        ).exit_code
        == 0
    )
    assert storage.get_promoted_release_id("agent_support", "local") == baseline_id

    hist = runner.invoke(cli, ["release", "history", "--agent", "agent_support", "--env", "local"])
    assert hist.exit_code == 0
    assert "rollback" in hist.output

def test_confidence_labels() -> None:
    assert (
        confidence_label(500, 500, min_baseline_runs=500, min_candidate_runs=500, min_low_runs=50) == "HIGH"
    )
    assert (
        confidence_label(200, 200, min_baseline_runs=500, min_candidate_runs=500, min_low_runs=50) == "MEDIUM"
    )
    assert (
        confidence_label(10, 200, min_baseline_runs=500, min_candidate_runs=500, min_low_runs=50) == "LOW"
    )


def test_end_to_end_local_diff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # init workspace config
    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0
    assert (tmp_path / "flightdeck.yaml").exists()

    assert runner.invoke(cli, ["policy", "set", str(write_policy(tmp_path))]).exit_code == 0

    # pricing import
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    res = runner.invoke(cli, ["pricing", "import", str(pricing)])
    assert res.exit_code == 0

    # duplicate import should fail unless --replace is passed
    res = runner.invoke(cli, ["pricing", "import", str(pricing)])
    assert res.exit_code != 0
    res = runner.invoke(cli, ["pricing", "import", "--replace", "--reason", "test replace", str(pricing)])
    assert res.exit_code == 0

    # register two releases
    r1_dir = write_release(tmp_path, agent_id="agent_support", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    r2_dir = write_release(tmp_path, agent_id="agent_support", version="2", pricing_provider="openai", pricing_version="openai-2026-04-30")
    res1 = runner.invoke(cli, ["release", "register", str(r1_dir)])
    res2 = runner.invoke(cli, ["release", "register", str(r2_dir)])
    assert res1.exit_code == 0
    assert res2.exit_code == 0
    rel1 = res1.output.strip()
    rel2 = res2.output.strip()
    assert rel1.startswith("rel_")
    assert rel2.startswith("rel_")

    res = runner.invoke(cli, ["release", "show", rel1])
    assert res.exit_code == 0
    assert '"release_id":' in res.output
    assert rel1 in res.output

    # ingest sample events (low volume => LOW confidence)
    now = datetime.now(tz=timezone.utc)
    events1 = write_events(tmp_path, release_id=rel1, agent_id="agent_support", n=10, ts=now)
    events2 = write_events(tmp_path, release_id=rel2, agent_id="agent_support", n=10, ts=now)
    res = runner.invoke(cli, ["runs", "ingest", str(events1)])
    assert res.exit_code == 0
    res = runner.invoke(cli, ["runs", "ingest", str(events2)])
    assert res.exit_code == 0

    res = runner.invoke(cli, ["release", "diff", rel1, rel2, "--window", "7d"])
    assert res.exit_code == 0
    assert "Confidence:" in res.output
    assert "LOW" in res.output
    assert "delta" in res.output
    assert "Î" not in res.output
    assert "Δ" not in res.output


def test_diff_rejects_cross_agent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    res = runner.invoke(cli, ["pricing", "import", str(pricing)])
    assert res.exit_code == 0

    r1_dir = write_release(tmp_path, agent_id="agent_one", version="1", pricing_provider="openai", pricing_version="openai-2026-04-30")
    r2_dir = write_release(tmp_path, agent_id="agent_two", version="2", pricing_provider="openai", pricing_version="openai-2026-04-30")
    rel1 = runner.invoke(cli, ["release", "register", str(r1_dir)]).output.strip()
    rel2 = runner.invoke(cli, ["release", "register", str(r2_dir)]).output.strip()

    res = runner.invoke(cli, ["release", "diff", rel1, rel2, "--window", "7d"])
    assert res.exit_code != 0


def test_pricing_show_and_missing_table_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    res = runner.invoke(cli, ["pricing", "import", str(pricing)])
    assert res.exit_code == 0

    res = runner.invoke(
        cli,
        ["pricing", "show", "--provider", "openai", "--version", "openai-2026-04-30"],
    )
    assert res.exit_code == 0
    assert '"provider": "openai"' in res.output
    assert '"pricing_version": "openai-2026-04-30"' in res.output

    res = runner.invoke(
        cli,
        ["pricing", "show", "--provider", "openai", "--version", "missing-version"],
    )
    assert res.exit_code != 0
    assert "Pricing table not found: openai/missing-version" in res.output


def test_diff_reports_missing_baseline_pricing_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    candidate_pricing = write_pricing(tmp_path, provider="openai", pricing_version="candidate-pricing")
    res = runner.invoke(cli, ["pricing", "import", str(candidate_pricing)])
    assert res.exit_code == 0

    baseline_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="missing-baseline",
    )
    candidate_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="candidate-pricing",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

    res = runner.invoke(cli, ["release", "diff", baseline_id, candidate_id, "--window", "7d"])
    assert res.exit_code != 0
    assert "Missing pricing table for baseline openai/missing-baseline" in res.output


def test_diff_reports_missing_candidate_pricing_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    baseline_pricing = write_pricing(tmp_path, provider="openai", pricing_version="baseline-pricing")
    res = runner.invoke(cli, ["pricing", "import", str(baseline_pricing)])
    assert res.exit_code == 0

    baseline_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="baseline-pricing",
    )
    candidate_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="missing-candidate",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

    res = runner.invoke(cli, ["release", "diff", baseline_id, candidate_id, "--window", "7d"])
    assert res.exit_code != 0
    assert "Missing pricing table for candidate openai/missing-candidate" in res.output


def test_diff_reports_missing_model_entry_in_pricing_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    pricing = write_pricing(
        tmp_path,
        provider="openai",
        pricing_version="openai-2026-04-30",
        model="other-model",
    )
    res = runner.invoke(cli, ["pricing", "import", str(pricing)])
    assert res.exit_code == 0

    baseline_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
        model="gpt-4.1-mini",
    )
    candidate_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
        model="gpt-4.1-mini",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    baseline_events = write_events(
        tmp_path,
        release_id=baseline_id,
        agent_id="agent_support",
        n=1,
        ts=now,
        model="gpt-4.1-mini",
    )
    candidate_events = write_events(
        tmp_path,
        release_id=candidate_id,
        agent_id="agent_support",
        n=1,
        ts=now,
        model="gpt-4.1-mini",
    )
    assert runner.invoke(cli, ["runs", "ingest", str(baseline_events)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(candidate_events)]).exit_code == 0

    res = runner.invoke(cli, ["release", "diff", baseline_id, candidate_id, "--window", "7d"])
    assert res.exit_code != 0
    assert "Pricing table missing model entry" in res.output
    assert "baseline_model=gpt-4.1-mini" in res.output
    assert "candidate_model=gpt-4.1-mini" in res.output


def test_diff_uses_separate_baseline_and_candidate_pricing_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    baseline_pricing = write_pricing(
        tmp_path,
        provider="openai",
        pricing_version="baseline-pricing",
        input_price=1.0,
        output_price=2.0,
    )
    candidate_pricing = write_pricing(
        tmp_path,
        provider="openai",
        pricing_version="candidate-pricing",
        input_price=3.0,
        output_price=4.0,
    )
    assert runner.invoke(cli, ["pricing", "import", str(baseline_pricing)]).exit_code == 0
    assert runner.invoke(cli, ["pricing", "import", str(candidate_pricing)]).exit_code == 0

    baseline_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="baseline-pricing",
    )
    candidate_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="2",
        pricing_provider="openai",
        pricing_version="candidate-pricing",
    )
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    baseline_events = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=1, ts=now)
    candidate_events = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=1, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(baseline_events)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(candidate_events)]).exit_code == 0

    res = runner.invoke(cli, ["release", "diff", baseline_id, candidate_id, "--window", "7d"])
    assert res.exit_code == 0
    assert "Baseline pricing: openai/baseline-pricing" in res.output
    assert "Candidate pricing: openai/candidate-pricing" in res.output
    assert "NOTE: cost delta includes pricing/model assumption changes" in res.output
    assert "Estimated model token cost/run (USD): 2.000000 -> 5.000000" in res.output


def test_policy_set_and_show(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    policy = write_policy(tmp_path, max_cost_per_run_usd=1.5)
    res = runner.invoke(cli, ["policy", "set", str(policy)])
    assert res.exit_code == 0
    assert "Set policy test-policy" in res.output

    res = runner.invoke(cli, ["policy", "show"])
    assert res.exit_code == 0
    assert '"policy_id": "test-policy"' in res.output
    assert '"max_cost_per_run_usd": 1.5' in res.output


def test_first_promotion_requires_reason_and_records_history(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    assert runner.invoke(cli, ["init"]).exit_code == 0
    pricing = write_pricing(tmp_path, provider="openai", pricing_version="openai-2026-04-30")
    assert runner.invoke(cli, ["pricing", "import", str(pricing)]).exit_code == 0

    release_dir = write_release(
        tmp_path,
        agent_id="agent_support",
        version="1",
        pricing_provider="openai",
        pricing_version="openai-2026-04-30",
    )
    release_id = runner.invoke(cli, ["release", "register", str(release_dir)]).output.strip()

    res = runner.invoke(cli, ["release", "promote", release_id, "--env", "local", "--window", "7d"])
    assert res.exit_code != 0
    assert "Missing option '--reason'" in res.output

    res = runner.invoke(
        cli,
        [
            "release",
            "promote",
            release_id,
            "--env",
            "local",
            "--window",
            "7d",
            "--reason",
            "initial production baseline",
        ],
    )
    assert res.exit_code == 0
    assert f"Promoted {release_id}" in res.output
    assert "Policy: PASS" in res.output

    res = runner.invoke(cli, ["release", "history", "--agent", "agent_support", "--env", "local"])
    assert res.exit_code == 0
    assert "promote" in res.output
    assert "PASS" in res.output
    assert "initial production baseline" in res.output
    assert release_id in res.output


def test_second_promotion_fails_when_policy_fails_and_keeps_current_release(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    assert runner.invoke(cli, ["init"]).exit_code == 0
    policy = write_policy(tmp_path, max_cost_per_run_usd=1.0)
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
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    baseline_events = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=5, ts=now)
    candidate_events = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=5, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(baseline_events)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(candidate_events)]).exit_code == 0

    res = runner.invoke(
        cli,
        [
            "release",
            "promote",
            baseline_id,
            "--env",
            "local",
            "--window",
            "7d",
            "--reason",
            "establish baseline",
        ],
    )
    assert res.exit_code == 0

    res = runner.invoke(
        cli,
        [
            "release",
            "promote",
            candidate_id,
            "--env",
            "local",
            "--window",
            "7d",
            "--reason",
            "try expensive candidate",
        ],
    )
    assert res.exit_code != 0
    assert "Policy: FAIL" in res.output
    assert "Promotion blocked by policy" in res.output
    assert "candidate cost_per_run_usd" in res.output

    storage = Storage(load_config().db_path)
    storage.migrate()
    assert storage.get_promoted_release_id("agent_support", "local") == baseline_id

    res = runner.invoke(cli, ["release", "history", "--agent", "agent_support", "--env", "local"])
    assert res.exit_code == 0
    assert "try expensive candidate" in res.output
    assert "FAIL" in res.output
    assert candidate_id in res.output


def test_passing_second_promotion_replaces_current_release(tmp_path: Path, monkeypatch) -> None:
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
    baseline_id = runner.invoke(cli, ["release", "register", str(baseline_dir)]).output.strip()
    candidate_id = runner.invoke(cli, ["release", "register", str(candidate_dir)]).output.strip()

    now = datetime.now(tz=timezone.utc)
    baseline_events = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=5, ts=now)
    candidate_events = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=5, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(baseline_events)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(candidate_events)]).exit_code == 0

    assert (
        runner.invoke(
            cli,
            [
                "release",
                "promote",
                baseline_id,
                "--env",
                "local",
                "--window",
                "7d",
                "--reason",
                "baseline",
            ],
        ).exit_code
        == 0
    )
    res = runner.invoke(
        cli,
        [
            "release",
            "promote",
            candidate_id,
            "--env",
            "local",
            "--window",
            "7d",
            "--reason",
            "safe candidate",
        ],
    )
    assert res.exit_code == 0
    assert f"Promoted {candidate_id}" in res.output

    storage = Storage(load_config().db_path)
    storage.migrate()
    assert storage.get_promoted_release_id("agent_support", "local") == candidate_id

