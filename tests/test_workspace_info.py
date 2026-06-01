"""Tests for ``flightdeck workspace info``.

Snapshot CLI that gives an operator a one-screen view of the workspace,
ledger, policy, and webhook state. Verify the human form contains the
expected sections and the JSON form is machine-parseable with all
documented keys.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from flightdeck.cli.main import cli


def test_workspace_info_human_format(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0

    res = runner.invoke(cli, ["workspace", "info"])
    assert res.exit_code == 0, res.output
    out = res.output

    # Section headers
    assert "FlightDeck workspace info" in out
    assert "Ledger" in out
    assert "Configuration" in out
    assert "Webhooks" in out

    # Counters present
    assert "releases" in out
    assert "promoted pointers" in out
    assert "audit actions" in out

    # Webhooks section reports zero on a fresh workspace
    assert "configured            0" in out
    assert "enabled               0" in out


def test_workspace_info_json_format(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0

    res = runner.invoke(cli, ["workspace", "info", "--json"])
    assert res.exit_code == 0, res.output

    payload = json.loads(res.output)

    # All documented top-level keys are present.
    expected_keys = {
        "workspace_path",
        "server_version",
        "db_backend",
        "db_target",
        "schema_version",
        "default_environment",
        "releases_total",
        "promoted_pointers_total",
        "actions_total",
        "run_events_total",
        "pricing_tables_total",
        "policy_configured",
        "pricing_catalog_configured",
        "pricing_catalog_path",
        "promotion_requires_approval",
        "webhooks_configured",
        "webhooks_enabled",
    }
    assert expected_keys <= set(payload.keys())

    # Fresh workspace: zero of everything ledger-related, sqlite backend,
    # schema at the current head, no webhooks.
    assert payload["db_backend"] == "sqlite"
    assert payload["releases_total"] == 0
    assert payload["promoted_pointers_total"] == 0
    assert payload["actions_total"] == 0
    assert payload["webhooks_configured"] == 0
    assert payload["webhooks_enabled"] == 0
    # Schema head is at least v5 (webhooks migration shipped in this PR).
    assert payload["schema_version"] >= 5
