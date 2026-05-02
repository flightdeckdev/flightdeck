"""Emit a RunEvent with Temporal-oriented labels (synthetic usage)."""

from __future__ import annotations

import argparse
import json
from uuid import uuid4

from flightdeck.integrations.common import make_run_end_event, temporal_labels
from flightdeck.sdk.client import FlightdeckClient


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8765")
    p.add_argument("--release-id", required=True)
    p.add_argument("--agent-id", required=True)
    p.add_argument("--environment", default="local")
    p.add_argument("--workflow-id", default="wf_example_001")
    p.add_argument("--workflow-run-id", default="")
    p.add_argument("--ingest", action="store_true")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    rid = uuid4().hex[:10]
    wf_run = args.workflow_run_id or None
    labels = {
        **temporal_labels(workflow_id=args.workflow_id, workflow_run_id=wf_run),
        "source": "examples/integration/adoption/temporal/emit_run.py",
    }
    ev = make_run_end_event(
        agent_id=args.agent_id,
        release_id=args.release_id,
        run_id=f"adopt-temporal-{rid}",
        tenant_id="tenant_example",
        task_id="task_example",
        environment=args.environment,
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=10,
        output_tokens=5,
        labels=labels,
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
