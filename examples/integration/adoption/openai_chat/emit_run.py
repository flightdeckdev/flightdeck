"""Emit one RunEvent from an OpenAI chat completion (synthetic, ingest, or live+ingest)."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from uuid import uuid4

from flightdeck.integrations.openai_chat import run_event_from_openai_chat_completion
from flightdeck.sdk.client import FlightdeckClient


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8765")
    p.add_argument("--release-id", required=True)
    p.add_argument("--agent-id", required=True)
    p.add_argument("--environment", default="local")
    p.add_argument(
        "--ingest",
        action="store_true",
        help="POST the built RunEvent to FlightDeck (otherwise print JSON only)",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Call OpenAI (requires OPENAI_API_KEY and flightdeck-ai[openai])",
    )
    return p.parse_args()


def _synthetic_response() -> object:
    usage = SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=40,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    return SimpleNamespace(model="gpt-4.1-mini", usage=usage)


def main() -> None:
    args = _parse_args()
    if args.live:
        from openai import OpenAI

        resp = OpenAI().chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Say ok in one word."}],
        )
    else:
        resp = _synthetic_response()

    rid = uuid4().hex[:10]
    ev = run_event_from_openai_chat_completion(
        resp,
        agent_id=args.agent_id,
        release_id=args.release_id,
        run_id=f"adopt-openai-{rid}",
        tenant_id="tenant_example",
        task_id="task_example",
        environment=args.environment,
        labels={"source": "examples/integration/adoption/openai_chat/emit_run.py"},
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
