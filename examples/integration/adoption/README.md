# Adoption hooks (framework examples)

These examples show how to turn **OpenAI**, **Anthropic**, **LangChain**, **OpenAI Agents SDK**,
**CrewAI-shaped totals**, or **Temporal** correlation metadata into **`RunEvent`** records and
emit them with **`FlightdeckClient.ingest_run_events`** (same contract as
**[../README.md](../README.md)**).

Installable helpers live under **`src/flightdeck/integrations/`** with optional **`pyproject.toml`**
extras; see **[docs/sdk-integrations.md](../../../docs/sdk-integrations.md)**.

## Python 3.14

This repository targets **CPython 3.14** only. Third-party wheels may lag; if an extra does not
install, run your agent in a **supported Python sidecar** and POST JSON to **`POST /v1/events`**
using the same **`RunEvent`** shape (**`schemas/v1/run_event.schema.json`**).

## Layout

| Directory | Notes |
|-----------|--------|
| [openai_chat/](openai_chat/) | Chat Completions → `RunEvent` |
| [anthropic_messages/](anthropic_messages/) | Messages API → `RunEvent` |
| [openai_agents/](openai_agents/) | Agents SDK result (duck-typed) → `RunEvent` |
| [langchain/](langchain/) | `FlightDeckLangChainCallbackHandler` |
| [crewai/](crewai/) | Totals via **`crewai_bridge`** (no `crewai` extra in the wheel; install CrewAI yourself if needed) |
| [temporal/](temporal/) | Suggested **`labels`** / **`run_id`** pattern |
