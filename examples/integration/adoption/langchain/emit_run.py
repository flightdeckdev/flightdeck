"""Accumulate LangChain-style LLM usage and emit one RunEvent."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from uuid import uuid4

from flightdeck.integrations.langchain_callback import FlightDeckLangChainCallbackHandler
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
    h = FlightDeckLangChainCallbackHandler(
        agent_id=args.agent_id,
        release_id=args.release_id,
        run_id=f"adopt-langchain-{rid}",
        tenant_id="tenant_example",
        task_id="task_example",
        environment=args.environment,
        labels={"source": "examples/integration/adoption/langchain/emit_run.py"},
    )
    llm_output = {
        "token_usage": {"prompt_tokens": 200, "completion_tokens": 60},
        "model_name": "gpt-4.1-mini",
    }
    h.on_llm_end(SimpleNamespace(generations=[], llm_output=llm_output))
    ev = h.to_run_event()
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
