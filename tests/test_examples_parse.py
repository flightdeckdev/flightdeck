from __future__ import annotations

import json
from pathlib import Path

import yaml

from flightdeck.models import ReleaseArtifact


def _iter_example_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1] / "examples"
    paths: list[Path] = []
    paths.extend(root.rglob("*.yaml"))
    paths.extend(root.rglob("*.yml"))
    paths.extend(root.rglob("*.jsonl"))
    return sorted(paths)


def test_example_yaml_files_parse_as_releases_or_pricing_or_policy() -> None:
    for path in _iter_example_files():
        if path.suffix.lower() not in {".yaml", ".yml"}:
            continue
        if "chart" in path.parts and "templates" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        assert isinstance(data, dict)

        kind = data.get("kind")
        if kind == "Release":
            ReleaseArtifact.model_validate(data)
        else:
            # pricing/policy/catalog examples are validated elsewhere; ensure YAML loads cleanly.
            assert (
                kind in {None, "WorkspaceConfig", "PricingCatalog"}
                or "provider" in data
                or "policy_id" in data
            )


def test_example_jsonl_lines_parse_as_json() -> None:
    for path in _iter_example_files():
        if path.suffix.lower() != ".jsonl":
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            json.loads(line)
