"""Post sample RunEvent payloads to a running flightdeck serve (POST /v1/events)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from uuid import uuid4

from flightdeck.models import RunEvent, RunEventMetrics, RunEventModelUsage, RunEventUsage
from flightdeck.sdk.client import FlightdeckClient


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8765", help="FlightDeck HTTP base URL")
    p.add_argument("--release-id", required=True, help="Registered release_id to attach events to")
    p.add_argument("--agent-id", required=True, help="Must match the registered release's agent_id")
    p.add_argument(
        "--environment",
        default="local",
        help="RunEvent.environment (default matches quickstart / default workspace env)",
    )
    p.add_argument("--dry-run", action="store_true", help="Print JSON payload only; do not POST")
    return p.parse_args()


def _sample_event(*, release_id: str, agent_id: str, environment: str) -> RunEvent:
    rid = uuid4().hex[:10]
    return RunEvent(
        timestamp=datetime.now(timezone.utc),
        agent_id=agent_id,
        release_id=release_id,
        run_id=f"emit-sample-{rid}",
        tenant_id="tenant_example",
        task_id="task_example",
        environment=environment,
        metrics=RunEventMetrics(latency_ms=250, success=True, error_type=None),
        usage=RunEventUsage(
            model=RunEventModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=400,
                output_tokens=120,
                cached_input_tokens=0,
            ),
        ),
        labels={"source": "examples/integration/emit_sample_events.py"},
    )


def main() -> None:
    args = _parse_args()
    ev = _sample_event(
        release_id=args.release_id,
        agent_id=args.agent_id,
        environment=args.environment,
    )
    if args.dry_run:
        payload = {"events": [ev.model_dump(mode="json")]}
        print(json.dumps(payload, indent=2))
        return
    client = FlightdeckClient(args.base_url.rstrip("/"))
    try:
        n = client.ingest_run_events([ev])
    finally:
        client.close()
    print(f"Inserted {n} event(s).")


if __name__ == "__main__":
    main()
