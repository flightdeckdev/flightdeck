from click.testing import CliRunner

from flightdeck import __version__
from flightdeck.cli.main import cli


def test_cli_help() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "FlightDeck" in result.output
    assert "AI Release Governance" in result.output


def test_cli_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output
