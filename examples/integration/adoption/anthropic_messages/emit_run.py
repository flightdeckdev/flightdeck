"""Emit one RunEvent from an Anthropic Messages response."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from uuid import uuid4

from flightdeck.integrations.anthropic_messages import run_event_from_anthropic_message
from flightdeck.sdk.client import FlightdeckClient


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8765")
    p.add_argument("--release-id", required=True)
    p.add_argument("--agent-id", required=True)
    p.add_argument("--environment", default="local")
    p.add_argument("--ingest", action="store_true")
    p.add_argument("--live", action="store_true")
    return p.parse_args()


def _synthetic_message() -> object:
    usage = SimpleNamespace(input_tokens=80, output_tokens=30, cache_read_input_tokens=0)
    return SimpleNamespace(model="claude-3-5-haiku-20241022", usage=usage)


def main() -> None:
    args = _parse_args()
    if args.live:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=32,
            messages=[{"role": "user", "content": "Say ok in one word."}],
        )
    else:
        msg = _synthetic_message()

    rid = uuid4().hex[:10]
    ev = run_event_from_anthropic_message(
        msg,
        agent_id=args.agent_id,
        release_id=args.release_id,
        run_id=f"adopt-anthropic-{rid}",
        tenant_id="tenant_example",
        task_id="task_example",
        environment=args.environment,
        labels={"source": "examples/integration/adoption/anthropic_messages/emit_run.py"},
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
