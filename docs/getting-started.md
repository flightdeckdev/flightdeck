# Getting started

## What the demo showed you

`flightdeck demo` ran the full FlightDeck loop in a throw-away temp directory. It registered
two agent releases (a baseline and a candidate), ingested one batch of run events into each,
diffed them to compute cost-per-run, latency, and error-rate deltas with a confidence label,
then promoted the baseline to `production`. Nothing left your machine — the workspace was
just a SQLite file in `/tmp`. That is the complete loop. The steps below wire the same loop
to your real agent.

---

## Before you start

You need a `flightdeck.yaml` workspace config in your working directory. Create one now:

```bash
pip install flightdeck-ai   # skip if already installed
flightdeck init
```

`init` writes `flightdeck.yaml`, creates `.flightdeck/flightdeck.db`, and imports bundled
OpenAI / Anthropic / Google pricing tables (`flightdeck-bundled-2026-05`) so you can run
diffs without assembling pricing YAMLs from scratch.

---

## Step 1 — Register your first release

A **release** is an immutable snapshot of your agent configuration: which model it uses, which
prompts, what pricing reference to apply. Every subsequent diff, promote, and rollback refers
back to these snapshots by ID.

Create a file called `release.yaml` alongside your agent code:

```yaml
api_version: v1
kind: Release
metadata:
  name: my-support-agent      # human label — shows up in `release list` output
  version: "1.0.0"            # free-form version string
spec:
  agent:
    agent_id: my-agent        # stable identifier — must match across all releases for the same agent
  runtime:
    provider: openai
    model: gpt-4o-mini        # must exist in the pricing table you imported
  prompts:
    system_ref: prompts/system.md   # path relative to the bundle directory
  pricing_reference:
    provider: openai
    pricing_version: flightdeck-bundled-2026-05   # matches the bundled table from `flightdeck init`
```

The only truly required fields are `api_version`, `kind`, `metadata.name`, `metadata.version`,
`spec.agent.agent_id`, `spec.runtime.provider`, `spec.runtime.model`, and
`spec.pricing_reference`. Everything else is optional.

Register it:

```bash
BASELINE=$(flightdeck release register ./release.yaml)
echo "Baseline release: $BASELINE"
# Baseline release: rel_abc123def456
```

`release register` accepts a single `release.yaml` file or a bundle directory containing
one. The ID it prints (`rel_…`) is what you will pass to ingest, diff, and promote.

See [release-artifact.md](release-artifact.md) for the full `release.yaml` field reference.

---

## Step 2 — Ingest run events from your agent

FlightDeck needs runtime evidence — cost, latency, error rate — before it can compute a
meaningful diff. Choose the path that fits your agent:

=== "Python SDK"

    Start `flightdeck serve` first, then emit events directly from your agent process:

    ```bash
    flightdeck serve &   # starts on 127.0.0.1:8765
    ```

    ```python
    import uuid
    from datetime import datetime, timezone
    from flightdeck.sdk import FlightdeckClient
    from flightdeck.models import RunEvent

    client = FlightdeckClient("http://127.0.0.1:8765")

    # Call once per agent run, right after the LLM responds
    event = RunEvent(
        timestamp=datetime.now(timezone.utc),
        agent_id="my-agent",           # must match spec.agent.agent_id in release.yaml
        release_id="rel_abc123def456", # from `flightdeck release register`
        run_id=str(uuid.uuid4()),      # unique per run — duplicates are silently skipped
        tenant_id="tenant_a",
        task_id="support_ticket",
        environment="production",
        usage={
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "input_tokens": 850,
                "output_tokens": 320,
            }
        },
        metrics={"success": True, "latency_ms": 740},
    )
    client.ingest_run_events([event])
    ```

    See [Python SDK](sdk.md) for the full client reference.

=== "HTTP POST /v1/events"

    If you prefer curl or are not using Python:

    ```bash
    curl -s -X POST http://127.0.0.1:8765/v1/events \
      -H "Content-Type: application/json" \
      -d '{
        "events": [{
          "timestamp": "2026-05-01T12:00:00Z",
          "agent_id": "my-agent",
          "release_id": "rel_abc123def456",
          "run_id": "run_unique_001",
          "tenant_id": "tenant_a",
          "task_id": "support_ticket",
          "environment": "production",
          "usage": {
            "model": {
              "provider": "openai",
              "model": "gpt-4o-mini",
              "input_tokens": 850,
              "output_tokens": 320
            }
          },
          "metrics": {"success": true, "latency_ms": 740}
        }]
      }'
    ```

    See [HTTP API reference](http-api.md#post-v1events) for the full field list.

=== "OpenAI integration"

    Wrap an existing `openai.chat.completions.create` call:

    ```python
    import uuid
    from flightdeck.sdk import FlightdeckClient
    from flightdeck.integrations.openai_chat import run_event_from_openai_chat_completion

    client = FlightdeckClient("http://127.0.0.1:8765")
    release_id = "rel_abc123def456"   # from `flightdeck release register`

    # Your existing OpenAI call (unchanged):
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": user_message}],
    )

    # Map the response to a RunEvent and emit it:
    event = run_event_from_openai_chat_completion(
        response,
        agent_id="my-agent",
        release_id=release_id,
        run_id=str(uuid.uuid4()),
        tenant_id="tenant_a",
        task_id="support_ticket",
        environment="production",
    )
    client.ingest_run_events([event])
    ```

    Install the extra: `pip install 'flightdeck-ai[openai]'`. See
    [SDK integrations](sdk-integrations.md) for Anthropic, LangChain, CrewAI, and Temporal.

---

## Step 3 — Run your first real diff

Once you have events for both a baseline and a candidate release, compare them:

```bash
flightdeck release diff $BASELINE $CANDIDATE --window 7d
```

Example output:

```
Window: 7d (2026-04-24T12:00:00+00:00 .. 2026-05-01T12:00:00+00:00)
Filters: env=local tenant=* task=*
Baseline pricing: openai/flightdeck-bundled-2026-05 (model=gpt-4o-mini)
Candidate pricing: openai/flightdeck-bundled-2026-05 (model=gpt-4o-mini)
Samples: baseline=420 candidate=380
Confidence: MEDIUM

Estimated model token cost/run (USD): 0.000312 -> 0.000289 (delta -0.000023, -7.37%)
Latency avg (ms): 820.00 -> 756.50 (delta -63.50)
Error rate: 0.0095 -> 0.0071 (delta -0.0024)

Policy: PASS
```

**What "Confidence: LOW" or "Confidence: MEDIUM" means:** FlightDeck compares your event
counts against the thresholds in your active policy (or the workspace defaults:
`min_candidate_runs=500`, `min_baseline_runs=500`). Below those thresholds the confidence
degrades to MEDIUM or LOW — the numbers are real but the sample is small. To get to HIGH:

1. Ingest more events (let the agent run longer).
2. Or lower the thresholds in your policy for a staging environment:

```yaml
# policy-staging.yaml
policy_id: staging
min_candidate_runs: 50
min_baseline_runs: 50
min_low_runs: 0
require_high_diff_confidence: false
```

The `--window` flag controls how far back events are pulled. Use `24h` for a daily gate or
`7d` for a weekly one. See [Operations & policy](operations-and-policy.md) for the full
confidence algorithm.

---

## Step 4 — Set a policy

A policy defines the maximum cost, latency, and error rate your candidate may not exceed
before promotion is blocked. Copy this to `policy.yaml` and tune the numbers to match your
agent's SLO:

```yaml
policy_id: prod-v1
max_cost_per_run_usd: 0.005   # block if candidate costs more than $0.005/run
max_error_rate: 0.02           # block if error rate exceeds 2%
max_latency_ms: 2000           # block if p-avg latency exceeds 2 s
require_high_diff_confidence: true
min_candidate_runs: 200
min_baseline_runs: 200
min_low_runs: 20
```

Load it:

```bash
flightdeck policy set policy.yaml
flightdeck policy show   # confirm the active policy
```

All `max_*` fields are optional — omit any you do not want to gate on. Only one policy is
active at a time. Setting a new one replaces the previous.

See [Operations & policy](operations-and-policy.md#policy-system) for the full policy model
and how all constraints are evaluated simultaneously.

---

## Step 5 — Promote when policy passes

The first promotion for an agent/environment is unconditional (no baseline exists yet to
diff against). After that, every promotion runs the active policy:

```bash
# First promotion — establishes the baseline pointer
flightdeck release promote $BASELINE --env production --window 7d \
  --reason "initial baseline for v1.0.0"

# Later: promote a candidate after policy passes
flightdeck release promote $CANDIDATE --env production --window 7d \
  --reason "v1.1.0: latency and cost improvements validated in staging"
```

What happens:

- The currently promoted release becomes the **baseline** for the diff.
- FlightDeck runs policy against the diff.
- On **PASS**: the promoted pointer is updated and an audit record is written.
- On **FAIL**: the attempt is still recorded (intent captured) but the pointer is not moved.

Check the history afterward:

```bash
flightdeck release history --agent my-agent --env production
```

The audit ledger is append-only. Every attempt — pass or fail — is recorded with timestamp,
actor, reason, and policy outcome.

---

## Next: CI integration

The `examples/ci/ledger_gate.py` script shows the canonical CI pattern: create a fresh
workspace, register both releases, ingest events, run `release diff --fail-on-policy`, then
clean up. The `--fail-on-policy` flag exits 1 when the diff's policy result is FAIL, which
makes CI block the deployment. GitHub Actions examples live in
`examples/ci/github-actions/`.

```bash
# The core CI gate in one shell session:
flightdeck init
BASELINE=$(flightdeck release register ./baseline-release)
CANDIDATE=$(flightdeck release register ./candidate-release)
flightdeck runs ingest baseline-events.jsonl
flightdeck runs ingest candidate-events.jsonl
flightdeck release diff $BASELINE $CANDIDATE --window 7d --fail-on-policy
```

See the [CLI reference](cli.md#common-patterns) for copy-paste recipes including policy-gated
CI steps and Slack webhook setup.

---

## Next: Web UI

Run `flightdeck serve` to open the web UI at `http://127.0.0.1:8765/`. The UI shows your
registered releases, promoted pointers, diff results, run forensics, and the audit ledger.
The `#/diff` page accepts `baseline`, `candidate`, `window`, and `environment` as URL
parameters so you can share a specific comparison as a link.

See [Web UI](web-ui.md) for the full page and component reference.
