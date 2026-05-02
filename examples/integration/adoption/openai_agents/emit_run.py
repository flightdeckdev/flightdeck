"""Emit a RunEvent from a synthetic OpenAI Agents-style result (usage dict)."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from uuid import uuid4

from flightdeck.integrations.openai_agents import run_event_from_openai_agents_result
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
    result = SimpleNamespace(
        usage={"input_tokens": 55, "output_tokens": 12, "model": "gpt-4.1-mini"},
    )
    rid = uuid4().hex[:10]
    ev = run_event_from_openai_agents_result(
        result,
        agent_id=args.agent_id,
        release_id=args.release_id,
        run_id=f"adopt-oai-agents-{rid}",
        tenant_id="tenant_example",
        task_id="task_example",
        environment=args.environment,
        labels={"source": "examples/integration/adoption/openai_agents/emit_run.py"},
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
