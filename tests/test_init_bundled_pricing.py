from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from flightdeck.bundled_pricing_bootstrap import BUNDLED_PRICING_VERSION, DEFAULT_CATALOG_RELATIVE_PATH
from flightdeck.cli.main import cli
from flightdeck.config import load_config
from flightdeck.storage import storage_from_config


def test_init_seeds_bundled_pricing_and_catalog(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0

    cfg = load_config(tmp_path / "flightdeck.yaml")
    assert cfg.pricing_catalog_path == DEFAULT_CATALOG_RELATIVE_PATH

    cat = tmp_path / DEFAULT_CATALOG_RELATIVE_PATH
    assert cat.is_file()
    data = yaml.safe_load(cat.read_text(encoding="utf-8"))
    assert data.get("kind") == "PricingCatalog"
    assert BUNDLED_PRICING_VERSION in str(data.get("catalog_version", ""))

    storage = storage_from_config(cfg)
    for provider in ("openai", "anthropic", "google"):
        t = storage.get_pricing_table(provider, BUNDLED_PRICING_VERSION)
        assert t is not None, f"missing {provider}"
        assert t.entries


def test_init_no_bundled_pricing_skips_imports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--no-bundled-pricing"]).exit_code == 0

    cfg = load_config(tmp_path / "flightdeck.yaml")
    assert cfg.pricing_catalog_path is None

    storage = storage_from_config(cfg)
    assert storage.get_pricing_table("openai", BUNDLED_PRICING_VERSION) is None

    assert not (tmp_path / ".flightdeck" / "pricing-catalog.yaml").is_file()


def test_bundled_resources_readable() -> None:
    from flightdeck.bundled_pricing_bootstrap import load_bundled_pricing_tables

    tables = load_bundled_pricing_tables()
    assert len(tables) == 3
    providers = {t.provider for t in tables}
    assert providers == {"openai", "anthropic", "google"}
