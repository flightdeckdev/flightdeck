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

## Module reference

Each submodule under `flightdeck.integrations` has a single responsibility: map
third-party SDK output into a `RunEvent`. Import only the submodule you need.

### `flightdeck.integrations.common` (no extras required)

Available as `from flightdeck.integrations import make_run_end_event, temporal_labels`.

#### `make_run_end_event(**kwargs) -> RunEvent`

Convenience constructor for a `type=run_end` `RunEvent`. All named parameters map
directly to fields on the v1 wire shape:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `agent_id` | yes | Stable agent ID |
| `release_id` | yes | Release ID from `flightdeck release register` |
| `run_id` | yes | Unique identifier; duplicates are skipped at ingest |
| `tenant_id` | yes | Tenant scoping dimension |
| `task_id` | yes | Task type dimension |
| `environment` | yes | Deployment environment |
| `provider` | yes | LLM provider (e.g. `"openai"`) |
| `model` | yes | Model name (e.g. `"gpt-4o"`) |
| `input_tokens` | yes | Prompt token count |
| `output_tokens` | yes | Completion token count |
| `cached_input_tokens` | no | Cached-prompt token count (default `0`) |
| `latency_ms` | no | End-to-end latency in milliseconds |
| `success` | no | Whether the run succeeded (default `True`) |
| `error_type` | no | Optional error class string |
| `trace_id`, `session_id`, `span_id` | no | Tracing identifiers (stored in `request.*`) |
| `labels` | no | Arbitrary string labels dict |
| `timestamp` | no | Event timestamp (defaults to `datetime.now(UTC)`) |
| `workspace_id` | no | Workspace identifier (default `"ws_local"`) |

#### `temporal_labels(*, workflow_id, workflow_run_id=None) -> dict[str, str]`

Returns a `labels` dict with `temporal.workflow_id` (and optionally `temporal.run_id`)
for tagging run events emitted from Temporal workflows. Pass the result as the `labels=`
argument to `make_run_end_event`.

### `flightdeck.integrations.openai_chat` (no extra needed; `openai` extra for the SDK itself)

#### `run_event_from_openai_chat_completion(response, *, agent_id, release_id, run_id, tenant_id, task_id, environment, **kwargs) -> RunEvent`

Constructs a `RunEvent` from an `openai.types.chat.ChatCompletion` response object.
Extracts `model`, `input_tokens`, `output_tokens`, and `cached_input_tokens` from
`response.usage`. Extra `kwargs` are passed to `make_run_end_event` (e.g. `latency_ms`,
`trace_id`). See `examples/integration/adoption/openai_chat/emit_run.py`.

### `flightdeck.integrations.anthropic_messages` (no extra needed; `anthropic` extra for the SDK itself)

#### `run_event_from_anthropic_message(message, *, agent_id, release_id, run_id, tenant_id, task_id, environment, **kwargs) -> RunEvent`

Constructs a `RunEvent` from an `anthropic.types.Message` object. Extracts `model`,
`input_tokens`, `output_tokens`, and `cache_read_input_tokens` from `message.usage`.
See `examples/integration/adoption/anthropic_messages/emit_run.py`.

### `flightdeck.integrations.openai_agents` (`integrations-openai-agents` extra)

#### `run_event_from_openai_agents_result(result, *, agent_id, release_id, run_id, tenant_id, task_id, environment, **kwargs) -> RunEvent`

Constructs a `RunEvent` from an OpenAI Agents SDK `RunResult` (or compatible object).
Aggregates token usage across all items in `result.raw_responses`. See
`examples/integration/adoption/openai_agents/emit_run.py`.

### `flightdeck.integrations.langchain_callback` (`integrations-langchain` extra)

#### `FlightDeckLangChainCallbackHandler`

A `BaseCallbackHandler` subclass. Pass an instance to LangChain chains or agents as
`callbacks=[handler]`. On `on_llm_end`, extracts token usage from the LLM result and
appends a `RunEvent` to `handler.events` (a list). After the chain completes, call
`client.ingest_run_events(handler.events)`. Constructor parameters:

| Parameter | Description |
|-----------|-------------|
| `agent_id` | Stable agent ID |
| `release_id` | Release ID |
| `run_id` | Unique run identifier (used for all events this handler captures) |
| `tenant_id`, `task_id`, `environment` | Standard scoping dimensions |

See `examples/integration/adoption/langchain/emit_run.py`.

### `flightdeck.integrations.crewai_bridge` (no extra; install `crewai` in your app env)

#### `run_event_from_crew_token_totals(input_tokens, output_tokens, *, model, provider, agent_id, release_id, run_id, tenant_id, task_id, environment, **kwargs) -> RunEvent`

Constructs a `RunEvent` from manually collected CrewAI token totals (no direct dependency
on CrewAI's internal classes). Collect totals from your crew's result callbacks and pass
them here. See `examples/integration/adoption/crewai/emit_totals.py`.

---

## Trust boundaries

Anyone who can reach **`POST /v1/events`** can append ledger rows. Keep **`flightdeck serve`**
on loopback or a private network unless you add your own controls. See **[SECURITY.md](../SECURITY.md)**.

## Examples

Copy-paste scripts: **[examples/integration/adoption/](../examples/integration/adoption/README.md)**.

## Policy boundary (contributors)

Contributor rules in **`AGENTS.md`** distinguish **in-product agent frameworks** (non-goals) from
these **narrow, opt-in adoption adapters**. Do not add a dynamic plugin registry.
