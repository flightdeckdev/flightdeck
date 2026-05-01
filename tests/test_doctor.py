from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from flightdeck.cli.main import cli
from flightdeck.models import PolicyResult, PromotionRecord
from flightdeck.storage import Storage

from tests.test_spine import write_events, write_policy, write_pricing, write_release


def test_doctor_passes_after_init(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    res = runner.invoke(cli, ["doctor"])
    assert res.exit_code == 0
    assert "schema_migrations" in res.output
    assert "all passed" in res.output.lower()


def test_doctor_audit_seq_ok_after_two_promotions(tmp_path: Path, monkeypatch) -> None:
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
    be = write_events(tmp_path, release_id=baseline_id, agent_id="agent_support", n=5, ts=now)
    ce = write_events(tmp_path, release_id=candidate_id, agent_id="agent_support", n=5, ts=now)
    assert runner.invoke(cli, ["runs", "ingest", str(be)]).exit_code == 0
    assert runner.invoke(cli, ["runs", "ingest", str(ce)]).exit_code == 0

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
    assert (
        runner.invoke(
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
                "roll",
            ],
        ).exit_code
        == 0
    )

    res = runner.invoke(cli, ["doctor"])
    assert res.exit_code == 0
    assert "audit_seq" in res.output
    assert "contiguous" in res.output.lower()


def test_doctor_fails_on_audit_seq_gap(tmp_path: Path, monkeypatch) -> None:
    test_doctor_audit_seq_ok_after_two_promotions(tmp_path, monkeypatch)
    db_path = tmp_path / ".flightdeck" / "flightdeck.db"
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE release_actions SET audit_seq = 99 WHERE audit_seq = 2")
    conn.commit()
    conn.close()

    res = CliRunner().invoke(cli, ["doctor"])
    assert res.exit_code != 0
    assert "audit_seq" in res.output.lower()


def test_insert_promotion_record_uses_immediate_transaction(tmp_path: Path) -> None:
    storage = Storage(str(tmp_path / "flightdeck.db"))
    storage.migrate()
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO releases
              (release_id, agent_id, version, environment, checksum, artifact_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("rel_1", "agent_support", "1", "local", "sha256:abc", "{}", "2026-05-01T00:00:00+00:00"),
        )

    record = PromotionRecord(
        action_id="act_1",
        action="promote",
        actor="tester",
        release_id="rel_1",
        agent_id="agent_support",
        environment="local",
        reason="test",
        policy_result=PolicyResult(passed=True),
        created_at=datetime.now(tz=timezone.utc),
    )

    competing_conn = storage.connect()
    try:
        competing_conn.execute("BEGIN IMMEDIATE;")
        try:
            storage.insert_promotion_record(record)
        except sqlite3.OperationalError as exc:
            assert "database is locked" in str(exc)
        else:
            raise AssertionError("insert_promotion_record did not request an immediate write lock")
    finally:
        competing_conn.rollback()
        competing_conn.close()


def test_doctor_fails_when_promoted_release_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    assert runner.invoke(cli, ["doctor"]).exit_code == 0

    db_path = tmp_path / ".flightdeck" / "flightdeck.db"
    assert db_path.is_file()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO promoted_releases (agent_id, environment, release_id, promoted_at)
        VALUES (?, ?, ?, ?)
        """,
        ("agent_x", "staging", "rel_missing", "2020-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    res = runner.invoke(cli, ["doctor"])
    assert res.exit_code != 0
    assert "rel_missing" in res.output or "missing" in res.output.lower()
