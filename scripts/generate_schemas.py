from __future__ import annotations

import json
from pathlib import Path

from flightdeck.models import Policy, PricingTable, ReleaseArtifact, RunEvent


def write_schema(path: Path, schema: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas" / "v1"
    write_schema(root / "release.schema.json", ReleaseArtifact.model_json_schema())
    write_schema(root / "run_event.schema.json", RunEvent.model_json_schema())
    write_schema(root / "pricing_table.schema.json", PricingTable.model_json_schema())
    write_schema(root / "policy.schema.json", Policy.model_json_schema())


if __name__ == "__main__":
    main()
