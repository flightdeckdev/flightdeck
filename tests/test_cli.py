import sqlite3

import pytest
from click.testing import CliRunner

from flightdeck import __version__
from flightdeck.cli.main import cli


def test_cli_help() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "FlightDeck" in result.output
    assert "Ship AI agents safely" in result.output


def test_cli_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_doctor_backup_writes_valid_sqlite(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    dest = tmp_path / "snap" / "ledger.db"
    res = runner.invoke(cli, ["doctor", "--backup", str(dest)])
    assert res.exit_code == 0
    assert dest.is_file()
    assert "Backed up database" in res.output
    con = sqlite3.connect(str(dest))
    try:
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='releases' LIMIT 1"
        ).fetchone()
        assert row is not None
    finally:
        con.close()
