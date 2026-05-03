# FlightDeck runtime integrations (experimental)

Optional Python helpers under **`flightdeck.integrations`** map third-party LLM and workflow
telemetry into **`RunEvent`** models for **`FlightdeckClient.ingest_run_events`** or JSONL ingest.
They strengthen **developer onboarding** and **runtime evidence**; they are **not** a second
product surface for orchestration.

## Stability and contracts

- **Normative wire shape:** **`schemas/v1/run_event.schema.json`** and **`POST /v1/events`**
  (same as **`flightdeck runs ingest`**). Treat the HTTP payload as the stable contract.
- **`flightdeck.integrations`:** SemVer-tracked but **experimental** until **`RELEASE_NOTES.md`**
  / **`CHANGELOG.md`** state otherwise. Helpers may change between minor releases as upstream SDKs
  evolve; pin **`flightdeck-ai`** if you depend on a specific mapper.
- **Core import rule:** **`import flightdeck`** does **not** install or import LangChain, Temporal,
  OpenAI Agents, etc. Import only the submodule you need (for example
  **`flightdeck.integrations.openai_chat`**) after installing the matching extra.

## Extras (see **`pyproject.toml`**)

| Extra | Purpose |
|-------|---------|
| **`openai`** | OpenAI Python client alongside FlightDeck (also used by examples) |
| **`anthropic`** | Anthropic Python client alongside FlightDeck |
| **`integrations-langchain`** | **`FlightDeckLangChainCallbackHandler`** in **`langchain_callback.py`** |
| **`integrations-temporal`** | Install **`temporalio`** next to FlightDeck when your worker shares a venv |
| **`integrations-openai-agents`** | **`openai-agents`** for result-shape experiments |
| **`integrations-ci`** | Meta-extra for CI: LangChain + Temporal + OpenAI Agents resolution |
| **`telemetry`** | OpenTelemetry SDK + OTLP exporter packages; wire with **`flightdeck.integrations.telemetry.configure_otel_tracing()`** (see below) |
| **`all`** | Convenience bundle including **`telemetry`** |

There is **no** **`crewai`** extra on the distribution. Use **`crewai_bridge.run_event_from_crew_token_totals`**
with totals you collect from CrewAI (or install **`crewai`** only in your application environment).

## OpenTelemetry (`telemetry` extra)

Install **`flightdeck-ai[telemetry]`** (or **`uv sync --extra telemetry`**), then once per process:

```python
from flightdeck.integrations.telemetry import configure_otel_tracing

configure_otel_tracing()
```

This registers an OpenTelemetry **SDK** `TracerProvider` with an **OTLP HTTP** span exporter and
batch processor. Set **`OTEL_EXPORTER_OTLP_ENDPOINT`** (for example
`http://127.0.0.1:4318/v1/traces`) and optional **`OTEL_EXPORTER_OTLP_HEADERS`** /
**`OTEL_SERVICE_NAME`** as documented for **`opentelemetry-exporter-otlp`**. Spans are sent to
**your** collector, not to FlightDeck as a vendor. A second call is a no-op unless you pass
**`force=True`** (rebinds the provider—use sparingly in tests).

FlightDeck does not auto-instrument **`httpx`** or the Python SDK; create spans in your app or
attach upstream auto-instrumentation if you need request-level traces.

## Trust boundaries

Anyone who can reach **`POST /v1/events`** can append ledger rows. Keep **`flightdeck serve`**
on loopback or a private network unless you add your own controls. See **[SECURITY.md](../SECURITY.md)**.

## Examples

Copy-paste scripts: **[examples/integration/adoption/](../examples/integration/adoption/README.md)**.

## Policy boundary (contributors)

Contributor rules in **`AGENTS.md`** distinguish **in-product agent frameworks** (non-goals) from
these **narrow, opt-in adoption adapters**. Do not add a dynamic plugin registry.
