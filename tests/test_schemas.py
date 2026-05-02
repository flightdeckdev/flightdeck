from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from flightdeck.models import Policy, PricingTable, ReleaseArtifact, RunEvent


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "json"


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("run_event_minimal_v1.json", RunEvent),
        ("release_artifact_minimal_v1.json", ReleaseArtifact),
        ("pricing_table_minimal_v1.json", PricingTable),
        ("policy_minimal_v1.json", Policy),
    ],
)
def test_minimal_json_fixture_validates(filename: str, model: type[BaseModel]) -> None:
    data = _read_json(_FIXTURE_DIR / filename)
    model.model_validate(data)


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("run_event_invalid_missing_release_id_v1.json", RunEvent),
        ("run_event_invalid_api_version_v0.json", RunEvent),
        ("policy_invalid_error_rate_gt_1_v1.json", Policy),
        ("pricing_table_invalid_negative_price_v1.json", PricingTable),
        ("release_artifact_invalid_wrong_kind_v1.json", ReleaseArtifact),
    ],
)
def test_invalid_json_fixture_rejected(filename: str, model: type[BaseModel]) -> None:
    data = _read_json(_FIXTURE_DIR / filename)
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_committed_json_schemas_match_models() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas" / "v1"

    assert _read_json(root / "release.schema.json") == ReleaseArtifact.model_json_schema()
    assert _read_json(root / "run_event.schema.json") == RunEvent.model_json_schema()
    assert _read_json(root / "pricing_table.schema.json") == PricingTable.model_json_schema()
    assert _read_json(root / "policy.schema.json") == Policy.model_json_schema()
