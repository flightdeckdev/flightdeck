# CrewAI-style totals → FlightDeck

There is **no** `crewai` wheel extra on **`flightdeck-ai`** (CrewAI pulls a very large resolver
graph). After **`Crew.kickoff()`**, take aggregated token totals from your telemetry and call
**`run_event_from_crew_token_totals`** from **`flightdeck.integrations.crewai_bridge`**.

```bash
uv sync --frozen --extra dev
uv run python examples/integration/adoption/crewai/emit_totals.py \
  --release-id rel_yourregisteredid --agent-id agent_support
```
