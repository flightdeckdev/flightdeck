from __future__ import annotations

from datetime import date

from click.testing import CliRunner

from flightdeck.bundled_pricing_age import (
    bundled_pricing_age_days,
    bundled_pricing_anchor_date,
    bundled_pricing_stale_warning,
    is_flightdeck_bundled_pricing_version,
)
from flightdeck.cli.main import cli
from flightdeck.config import load_config
from flightdeck.operations import compute_diff
from flightdeck.storage import storage_from_config

from tests.test_spine import write_policy, write_release


def test_bundled_pricing_anchor_and_age() -> None:
    assert bundled_pricing_anchor_date("flightdeck-bundled-2026-05") == date(2026, 5, 1)
    assert bundled_pricing_anchor_date("openai-2026-04-30") is None
    assert is_flightdeck_bundled_pricing_version("flightdeck-bundled-2026-05") is True
    assert is_flightdeck_bundled_pricing_version("custom-v1") is False
    age = bundled_pricing_age_days("flightdeck-bundled-2026-05", today=date(2026, 5, 3))
    assert age == 2


def test_stale_warning_when_old() -> None:
    w = bundled_pricing_stale_warning(
        "flightdeck-bundled-2026-05",
        today=date(2026, 9, 1),
        max_age_days=90,
        role="baseline",
    )
    assert w is not None
    assert "baseline" in w
    assert "flightdeck-bundled-2026-05" in w


def test_no_stale_warning_when_fresh() -> None:
    assert (
        bundled_pricing_stale_warning(
            "flightdeck-bundled-2026-05",
            today=date(2026, 5, 20),
            max_age_days=90,
        )
        is None
    )


def test_pricing_check_cli_ok_and_stale_exit(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    monkeypatch.setattr(
        "flightdeck.bundled_pricing_age.pricing_stale_check_date",
        lambda: date(2026, 5, 10),
    )
    r_ok = runner.invoke(cli, ["pricing", "check", "--max-age-days", "90"])
    assert r_ok.exit_code == 0
    assert "OK" in r_ok.output
    assert "flightdeck-bundled-2026-05" in r_ok.output

    monkeypatch.setattr(
        "flightdeck.bundled_pricing_age.pricing_stale_check_date",
        lambda: date(2026, 9, 1),
    )
    r_warn = runner.invoke(cli, ["pricing", "check", "--max-age-days", "90"])
    assert r_warn.exit_code == 0
    assert "STALE" in r_warn.output

    r_fail = runner.invoke(cli, ["pricing", "check", "--max-age-days", "90", "--fail"])
    assert r_fail.exit_code == 1


def test_compute_diff_single_stale_warning_same_bundled_version(tmp_path, monkeypatch) -> None:
    """Baseline and candidate sharing one bundled version emit one staleness warning."""
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

    r1 = write_release(
        tmp_path,
        agent_id="agent_x",
        version="1",
        pricing_provider="openai",
        pricing_version="flightdeck-bundled-2026-05",
        model="gpt-4o-mini",
    )
    r2 = write_release(
        tmp_path,
        agent_id="agent_x",
        version="2",
        pricing_provider="openai",
        pricing_version="flightdeck-bundled-2026-05",
        model="gpt-4o-mini",
    )
    rel1 = runner.invoke(cli, ["release", "register", str(r1)]).output.strip()
    rel2 = runner.invoke(cli, ["release", "register", str(r2)]).output.strip()

    monkeypatch.setattr(
        "flightdeck.bundled_pricing_age.pricing_stale_check_date",
        lambda: date(2026, 9, 1),
    )

    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()
    out = compute_diff(
        cfg=cfg,
        storage=storage,
        baseline_release_id=rel1,
        candidate_release_id=rel2,
        window="7d",
        environment="local",
        tenant_id=None,
        task_id=None,
    )
    stale_msgs = [w for w in out.pricing_warnings if "bundled snapshot" in w]
    assert len(stale_msgs) == 1
    assert "flightdeck-bundled-2026-05" in stale_msgs[0]
