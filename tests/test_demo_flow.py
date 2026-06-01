"""Tests for bundled quickstart resolution and demo flow helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from flightdeck import demo_flow
from flightdeck.cli.main import cli


def test_quickstart_root_prefers_repo_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLIGHTDECK_QUICKSTART_ROOT", raising=False)
    repo_root = Path(demo_flow.__file__).resolve().parents[2]
    examples = repo_root / "examples" / "quickstart"
    if not examples.is_dir():
        pytest.skip("examples/quickstart not present in this checkout")

    assert demo_flow.quickstart_root() == examples.resolve()


def test_quickstart_root_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qs = tmp_path / "qs"
    qs.mkdir()
    (qs / "policy.yaml").write_text("policy_id: x\n", encoding="utf-8")
    monkeypatch.setenv("FLIGHTDECK_QUICKSTART_ROOT", str(qs))

    assert demo_flow.quickstart_root() == qs.resolve()


def test_demo_session_keep_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path(demo_flow.__file__).resolve().parents[2]
    examples = repo_root / "examples" / "quickstart"
    if not examples.is_dir():
        pytest.skip("examples/quickstart not present")

    monkeypatch.delenv("FLIGHTDECK_QUICKSTART_ROOT", raising=False)
    ws = demo_flow.demo_session(
        verify=False,
        doctor=False,
        qs_dir=None,
        promote_reason="pytest demo",
        keep_workspace=True,
    )
    assert ws is not None
    cfg = ws / "flightdeck.yaml"
    assert cfg.is_file()


def test_demo_cli_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root)
    runner = CliRunner()
    res = runner.invoke(cli, ["demo"])
    assert res.exit_code == 0, res.output
    assert "Demo OK" in res.output


def test_demo_session_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path(demo_flow.__file__).resolve().parents[2]
    examples = repo_root / "examples" / "quickstart"
    if not examples.is_dir():
        pytest.skip("examples/quickstart not present")

    monkeypatch.delenv("FLIGHTDECK_QUICKSTART_ROOT", raising=False)
    ws = demo_flow.demo_session(
        verify=False,
        doctor=False,
        qs_dir=None,
        promote_reason="pytest demo",
        keep_workspace=False,
    )
    assert ws is None

