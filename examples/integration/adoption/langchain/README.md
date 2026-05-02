# LangChain Core → FlightDeck

```bash
uv sync --frozen --extra dev --extra integrations-langchain
uv run python examples/integration/adoption/langchain/emit_run.py \
  --release-id rel_yourregisteredid --agent-id agent_support
```

Uses **`FlightDeckLangChainCallbackHandler`** with a synthetic **`on_llm_end`** payload (no LLM network call).
