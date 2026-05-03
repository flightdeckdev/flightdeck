from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from click.testing import CliRunner

from flightdeck.cli.main import cli

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "golden_bundle"


def test_release_verify_ok(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    bundle = tmp_path / "bundle"
    shutil.copytree(FIXTURE, bundle)

    assert runner.invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    pricing = {
        "provider": "openai",
        "pricing_version": "p",
        "entries": [{"model": "m", "input_usd_per_1k_tokens": 1.0, "output_usd_per_1k_tokens": 2.0}],
    }
    pp = tmp_path / "pricing.yaml"
    pp.write_text(yaml.safe_dump(pricing, sort_keys=False), encoding="utf-8")
    assert runner.invoke(cli, ["pricing", "import", str(pp)]).exit_code == 0

    rid = runner.invoke(cli, ["release", "register", str(bundle)]).output.strip()
    res = runner.invoke(cli, ["release", "verify", rid, "--path", str(bundle)])
    assert res.exit_code == 0
    assert "OK: checksum matches" in res.output


def test_release_verify_exit_2_on_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    bundle = tmp_path / "bundle"
    shutil.copytree(FIXTURE, bundle)

    assert runner.invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0
    pricing = {
        "provider": "openai",
        "pricing_version": "p",
        "entries": [{"model": "m", "input_usd_per_1k_tokens": 1.0, "output_usd_per_1k_tokens": 2.0}],
    }
    pp = tmp_path / "pricing.yaml"
    pp.write_text(yaml.safe_dump(pricing, sort_keys=False), encoding="utf-8")
    assert runner.invoke(cli, ["pricing", "import", str(pp)]).exit_code == 0

    rid = runner.invoke(cli, ["release", "register", str(bundle)]).output.strip()
    (bundle / "prompts" / "s.md").write_text("tampered\n", encoding="utf-8", newline="\n")
    res = runner.invoke(cli, ["release", "verify", rid, "--path", str(bundle)])
    assert res.exit_code == 2
    assert "CHECKSUM MISMATCH" in res.output
