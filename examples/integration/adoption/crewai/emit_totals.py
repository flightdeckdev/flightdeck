"""Emit a RunEvent from explicit token totals (CrewAI-style manual aggregation)."""

from __future__ import annotations

import argparse
import json
from uuid import uuid4

from flightdeck.integrations.crewai_bridge import run_event_from_crew_token_totals
from flightdeck.sdk.client import FlightdeckClient


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8765")
    p.add_argument("--release-id", required=True)
    p.add_argument("--agent-id", required=True)
    p.add_argument("--environment", default="local")
    p.add_argument("--ingest", action="store_true")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    rid = uuid4().hex[:10]
    ev = run_event_from_crew_token_totals(
        agent_id=args.agent_id,
        release_id=args.release_id,
        run_id=f"adopt-crewai-{rid}",
        tenant_id="tenant_example",
        task_id="task_example",
        environment=args.environment,
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=500,
        output_tokens=120,
        crew_name="example_crew",
        labels={"source": "examples/integration/adoption/crewai/emit_totals.py"},
    )
    if not args.ingest:
        print(json.dumps({"events": [ev.model_dump(mode="json")]}, indent=2))
        return
    client = FlightdeckClient(args.base_url.rstrip("/"))
    try:
        n = client.ingest_run_events([ev])
    finally:
        client.close()
    print(f"Inserted {n} event(s).")


if __name__ == "__main__":
    main()
