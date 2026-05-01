"""FlightDeck CLI - AI Release Governance."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import click
import yaml
from click.exceptions import Exit as ClickExit

from flightdeck import __version__
from flightdeck.bundle import bundle_checksum
from flightdeck.config import DEFAULT_CONFIG_FILENAME, load_config, write_default_config
from flightdeck.doctor import run_doctor
from flightdeck.ledger import diff_releases, parse_window
from flightdeck.models import (
    Policy,
    PolicyResult,
    PricingTable,
    PromotionRecord,
    ReleaseArtifact,
    ReleaseRecord,
    RunEvent,
    utc_now,
)
from flightdeck.storage import Storage


def read_release_artifact(path: Path) -> ReleaseArtifact:
    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    return ReleaseArtifact.model_validate(data)


def default_policy() -> Policy:
    # When no policy file is set, match Policy model defaults (strict diff confidence for v1 track).
    # Demos and tests set an explicit policy YAML (e.g. require_high_diff_confidence: false) where needed.
    return Policy(
        max_cost_per_run_usd=None,
        max_latency_ms=None,
        max_error_rate=None,
    )


def actor_name() -> str:
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def parse_events_file(path: Path) -> list[RunEvent]:
    events: list[RunEvent] = []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        data = json.loads(text)
        for item in data:
            events.append(RunEvent.model_validate(item))
        return events

    for line in text.splitlines():
        if not line.strip():
            continue
        events.append(RunEvent.model_validate_json(line))
    return events


@click.group()
@click.version_option(version=__version__, prog_name="flightdeck")
def cli() -> None:
    """FlightDeck - AI Release Governance (release safety ledger + trustworthy diffs)."""


@cli.command()
@click.option("--path", "path_", default=DEFAULT_CONFIG_FILENAME, show_default=True)
def init(path_: str) -> None:
    """Create a local `flightdeck.yaml` workspace config."""
    p = Path(path_)
    if p.exists():
        raise click.ClickException(f"{p} already exists")
    written = write_default_config(p)
    click.echo(f"Wrote {written}")


@cli.command("doctor")
def doctor_cmd() -> None:
    """Run read-only health checks on the local ledger (migrations, promoted pointers)."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    checks = run_doctor(storage)
    failed = False
    for c in checks:
        prefix = "ok  " if c.ok else "FAIL"
        line = f"{prefix}  {c.name}: {c.detail}"
        if c.ok:
            click.echo(line)
        else:
            click.echo(click.style(line, fg="red"), err=True)
            failed = True
    if failed:
        raise click.ClickException("Doctor found one or more problems.")
    click.echo(f"Doctor: {len(checks)} check(s), all passed.")


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True)
@click.option("--reload", is_flag=True, default=False)
def serve(host: str, port: int, reload: bool) -> None:
    """Start the local FlightDeck HTTP service (event ingestion)."""
    import uvicorn

    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    if host.strip() not in loopback_hosts:
        click.echo(
            f"Warning: binding to {host!r} exposes HTTP ingest without authentication; "
            "use only on trusted networks (see https://github.com/flightdeckdev/flightdeck/blob/main/docs/spec-v1-forward.md §4).",
            err=True,
        )

    uvicorn.run(
        "flightdeck.server.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


@cli.group()
def release() -> None:
    """Work with Release artifacts."""


@release.command("register")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--env", "environment", default=None, help="Override environment for this registration.")
def release_register(path: Path, environment: str | None) -> None:
    """Register an immutable Release artifact (file or bundle directory)."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    env = environment or cfg.default_environment

    release_yaml = path / "release.yaml" if path.is_dir() else path
    if not release_yaml.exists():
        raise click.ClickException(f"Release artifact not found: {release_yaml}")

    artifact = read_release_artifact(release_yaml)
    checksum = bundle_checksum(path)
    release_id = f"rel_{uuid4().hex[:12]}"

    record = ReleaseRecord(
        release_id=release_id,
        agent_id=artifact.spec.agent.agent_id,
        version=artifact.metadata.version,
        environment=env,
        checksum=checksum,
        artifact_json=artifact.model_dump(mode="json"),
        created_at=utc_now(),
    )
    storage.insert_release(record)
    click.echo(release_id)


@release.command("list")
def release_list() -> None:
    """List registered releases."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()
    for r in storage.list_releases():
        click.echo(f"{r.release_id}\t{r.agent_id}\t{r.version}\t{r.environment}\t{r.created_at.isoformat()}")


@release.command("show")
@click.argument("release_id")
def release_show(release_id: str) -> None:
    """Show a registered release record as JSON."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    record = storage.get_release(release_id)
    if not record:
        raise click.ClickException(f"Unknown release: {release_id}")

    click.echo(record.model_dump_json(indent=2))


@release.command("verify")
@click.argument("release_id")
@click.option(
    "--path",
    "artifact_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Bundle directory (or single release.yaml) on disk to hash and compare to the registered checksum.",
)
def release_verify(release_id: str, artifact_path: Path) -> None:
    """Verify on-disk artifact bytes match the checksum stored at registration (exit 2 on mismatch)."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    record = storage.get_release(release_id)
    if not record:
        raise click.ClickException(f"Unknown release: {release_id}")

    stored = record.checksum
    actual = bundle_checksum(artifact_path)
    if stored == actual:
        click.echo(f"OK: checksum matches for {release_id}")
        click.echo(f"  sha256={stored}")
        return

    click.echo(
        f"CHECKSUM MISMATCH for {release_id}\n"
        f"  stored (DB):      {stored}\n"
        f"  recomputed (disk): {actual}\n"
        "Disk content differs from registration (files, line endings, or hashing rules).",
        err=True,
    )
    raise ClickExit(2)


@cli.group()
def pricing() -> None:
    """Import and view pricing tables."""


@pricing.command("import")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--replace", is_flag=True, default=False, help="Replace an existing pricing version (audit-sensitive).")
@click.option(
    "--reason",
    default=None,
    help="Required when using --replace (stored in the pricing import audit log).",
)
def pricing_import(path: Path, replace: bool, reason: str | None) -> None:
    """Import a pricing table YAML."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    table = PricingTable.model_validate(data)
    try:
        storage.insert_pricing_table(table, replace=replace, actor=actor_name(), reason=reason)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    verb = "Replaced" if replace else "Imported"
    click.echo(f"{verb} {table.provider}/{table.pricing_version}")


@pricing.command("show")
@click.option("--provider", required=True)
@click.option("--version", "pricing_version", required=True)
def pricing_show(provider: str, pricing_version: str) -> None:
    """Show a pricing table by provider/version."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    table = storage.get_pricing_table(provider, pricing_version)
    if not table:
        raise click.ClickException(f"Pricing table not found: {provider}/{pricing_version}")
    click.echo(table.model_dump_json(indent=2))


@cli.group()
def policy() -> None:
    """Set and view promotion policy."""


@policy.command("set")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def policy_set(path: Path) -> None:
    """Set the active promotion policy from YAML."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    p = Policy.model_validate(data)
    storage.set_active_policy(p)
    click.echo(f"Set policy {p.policy_id}")


@policy.command("show")
def policy_show() -> None:
    """Show the active promotion policy."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    p = storage.get_active_policy() or default_policy()
    click.echo(p.model_dump_json(indent=2))


@cli.group()
def runs() -> None:
    """Ingest run events."""


@runs.command("ingest")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def runs_ingest(path: Path) -> None:
    """Ingest RunEvent JSONL (or JSON array) into local storage."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    events = parse_events_file(path)
    inserted = storage.insert_run_events(events)
    click.echo(f"Inserted {inserted} events")


@release.command("diff")
@click.argument("baseline_release_id")
@click.argument("candidate_release_id")
@click.option("--window", required=True, help="Required. Time window like 7d, 24h, 30m.")
@click.option("--tenant", "tenant_id", default=None)
@click.option("--task", "task_id", default=None)
@click.option("--env", "environment", default=None)
def release_diff(
    baseline_release_id: str,
    candidate_release_id: str,
    window: str,
    tenant_id: str | None,
    task_id: str | None,
    environment: str | None,
) -> None:
    """Compare two releases over a time window and print a confidence-labeled safety diff."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    base = storage.get_release(baseline_release_id)
    cand = storage.get_release(candidate_release_id)
    if not base:
        raise click.ClickException(f"Unknown baseline release: {baseline_release_id}")
    if not cand:
        raise click.ClickException(f"Unknown candidate release: {candidate_release_id}")

    env = environment or cfg.default_environment

    # Load artifacts and enforce same agent_id unless an explicit escape hatch exists later.
    base_artifact = ReleaseArtifact.model_validate(base.artifact_json)
    cand_artifact = ReleaseArtifact.model_validate(cand.artifact_json)
    if base_artifact.spec.agent.agent_id != cand_artifact.spec.agent.agent_id:
        raise click.ClickException(
            "Cross-agent diff is not allowed. "
            f"Baseline agent_id={base_artifact.spec.agent.agent_id}, "
            f"candidate agent_id={cand_artifact.spec.agent.agent_id}."
        )

    base_pricing_ref = base_artifact.spec.pricing_reference
    cand_pricing_ref = cand_artifact.spec.pricing_reference

    base_table = storage.get_pricing_table(base_pricing_ref.provider, base_pricing_ref.pricing_version)
    if not base_table:
        raise click.ClickException(
            f"Missing pricing table for baseline {base_pricing_ref.provider}/{base_pricing_ref.pricing_version}. "
            f"Run `flightdeck pricing import ...`."
        )

    cand_table = storage.get_pricing_table(cand_pricing_ref.provider, cand_pricing_ref.pricing_version)
    if not cand_table:
        raise click.ClickException(
            f"Missing pricing table for candidate {cand_pricing_ref.provider}/{cand_pricing_ref.pricing_version}. "
            f"Run `flightdeck pricing import ...`."
        )

    try:
        delta = parse_window(window)
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    until = utc_now()
    since = until - delta

    baseline_events = storage.query_runs(
        baseline_release_id,
        since,
        until,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=env,
    )
    candidate_events = storage.query_runs(
        candidate_release_id,
        since,
        until,
        tenant_id=tenant_id,
        task_id=task_id,
        environment=env,
    )

    policy = storage.get_active_policy() or default_policy()
    try:
        result = diff_releases(
            cfg=cfg,
            policy=policy,
            baseline_events=baseline_events,
            candidate_events=candidate_events,
            baseline_pricing_table=base_table,
            candidate_pricing_table=cand_table,
            window=window,
        )
    except KeyError as e:
        # Make missing-model pricing failures explicit and actionable.
        raise click.ClickException(
            f"Pricing table missing model entry. "
            f"baseline_model={base_artifact.spec.runtime.model} "
            f"candidate_model={cand_artifact.spec.runtime.model}. "
            f"Check pricing tables: "
            f"{base_pricing_ref.provider}/{base_pricing_ref.pricing_version} and "
            f"{cand_pricing_ref.provider}/{cand_pricing_ref.pricing_version}."
        ) from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    click.echo(f"Window: {window} ({since.isoformat()} .. {until.isoformat()})")
    click.echo(f"Filters: env={env} tenant={tenant_id or '*'} task={task_id or '*'}")
    click.echo(
        f"Baseline pricing: {base_pricing_ref.provider}/{base_pricing_ref.pricing_version} "
        f"(model={base_artifact.spec.runtime.model})"
    )
    click.echo(
        f"Candidate pricing: {cand_pricing_ref.provider}/{cand_pricing_ref.pricing_version} "
        f"(model={cand_artifact.spec.runtime.model})"
    )
    if (
        base_pricing_ref.provider != cand_pricing_ref.provider
        or base_pricing_ref.pricing_version != cand_pricing_ref.pricing_version
        or base_artifact.spec.runtime.model != cand_artifact.spec.runtime.model
    ):
        click.echo(
            "NOTE: cost delta includes pricing/model assumption changes (pricing reference and/or model differ)."
        )
    click.echo(f"Samples: baseline={result.baseline_runs} candidate={result.candidate_runs}")
    click.echo(f"Confidence: {result.confidence}" + (f" ({result.confidence_reason})" if result.confidence_reason else ""))
    click.echo("")
    click.echo(
        f"Estimated model token cost/run (USD): {result.baseline.cost_per_run_usd:.6f} -> {result.candidate.cost_per_run_usd:.6f} "
        f"(delta {result.delta_cost_per_run_usd:+.6f}"
        + (f", {result.delta_cost_per_run_pct:+.2%})" if result.delta_cost_per_run_pct is not None else ")")
    )
    if result.baseline.latency_ms_avg is not None and result.candidate.latency_ms_avg is not None:
        click.echo(
            f"Latency avg (ms): {result.baseline.latency_ms_avg:.2f} -> {result.candidate.latency_ms_avg:.2f} "
            f"(delta {result.delta_latency_ms_avg:+.2f})"
        )
    click.echo(
        f"Error rate: {result.baseline.error_rate:.4f} -> {result.candidate.error_rate:.4f} "
        f"(delta {result.delta_error_rate:+.4f})"
    )
    click.echo("")
    click.echo("Policy: " + ("PASS" if result.policy.passed else "FAIL"))
    for r in result.policy.reasons:
        click.echo(f"- {r}")


@release.command("promote")
@click.argument("release_id")
@click.option("--env", "environment", required=True)
@click.option("--window", required=True, help="Required. Time window like 7d, 24h, 30m.")
@click.option("--reason", required=True, help="Required rationale for the promotion decision.")
def release_promote(release_id: str, environment: str, window: str, reason: str) -> None:
    """Promote a release after evaluating active policy against the current baseline."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    target = storage.get_release(release_id)
    if not target:
        raise click.ClickException(f"Unknown release: {release_id}")

    target_artifact = ReleaseArtifact.model_validate(target.artifact_json)
    agent_id = target_artifact.spec.agent.agent_id
    active_policy = storage.get_active_policy() or default_policy()
    current_release_id = storage.get_promoted_release_id(agent_id, environment)

    policy_result: PolicyResult
    if not current_release_id:
        policy_result = PolicyResult(
            passed=True,
            reasons=["first promotion: no promoted baseline for agent/environment"],
        )
    else:
        baseline = storage.get_release(current_release_id)
        if not baseline:
            raise click.ClickException(f"Promoted baseline release is missing: {current_release_id}")

        baseline_artifact = ReleaseArtifact.model_validate(baseline.artifact_json)
        baseline_pricing_ref = baseline_artifact.spec.pricing_reference
        candidate_pricing_ref = target_artifact.spec.pricing_reference

        baseline_table = storage.get_pricing_table(
            baseline_pricing_ref.provider,
            baseline_pricing_ref.pricing_version,
        )
        if not baseline_table:
            raise click.ClickException(
                "Missing pricing table for promoted baseline "
                f"{baseline_pricing_ref.provider}/{baseline_pricing_ref.pricing_version}. "
                "Run `flightdeck pricing import ...`."
            )

        candidate_table = storage.get_pricing_table(
            candidate_pricing_ref.provider,
            candidate_pricing_ref.pricing_version,
        )
        if not candidate_table:
            raise click.ClickException(
                "Missing pricing table for candidate "
                f"{candidate_pricing_ref.provider}/{candidate_pricing_ref.pricing_version}. "
                "Run `flightdeck pricing import ...`."
            )

        try:
            delta = parse_window(window)
        except ValueError as e:
            raise click.ClickException(str(e)) from e
        until = utc_now()
        since = until - delta
        baseline_events = storage.query_runs(
            current_release_id,
            since,
            until,
            environment=environment,
        )
        candidate_events = storage.query_runs(
            release_id,
            since,
            until,
            environment=environment,
        )

        try:
            diff = diff_releases(
                cfg=cfg,
                policy=active_policy,
                baseline_events=baseline_events,
                candidate_events=candidate_events,
                baseline_pricing_table=baseline_table,
                candidate_pricing_table=candidate_table,
                window=window,
            )
        except KeyError as e:
            raise click.ClickException(
                "Pricing table missing model entry. "
                f"baseline_model={baseline_artifact.spec.runtime.model} "
                f"candidate_model={target_artifact.spec.runtime.model}."
            ) from e
        except ValueError as e:
            raise click.ClickException(str(e)) from e
        policy_result = diff.policy

    record = PromotionRecord(
        action_id=f"act_{uuid4().hex[:12]}",
        action="promote",
        actor=actor_name(),
        release_id=release_id,
        agent_id=agent_id,
        environment=environment,
        reason=reason,
        policy_result=policy_result,
        baseline_release_id=current_release_id,
        created_at=utc_now(),
    )

    if not policy_result.passed:
        storage.insert_promotion_record(record)
        click.echo("Policy: FAIL")
        for r in policy_result.reasons:
            click.echo(f"- {r}")
        raise click.ClickException("Promotion blocked by policy")

    storage.commit_promotion(record, new_promoted_release_id=release_id)
    click.echo(f"Promoted {release_id} for {agent_id}/{environment}")
    click.echo("Policy: PASS")
    for r in policy_result.reasons:
        click.echo(f"- {r}")


@release.command("rollback")
@click.argument("release_id")
@click.option("--env", "environment", required=True)
@click.option("--window", required=True, help="Required. Time window like 7d, 24h, 30m.")
@click.option("--reason", required=True, help="Required rationale for the rollback decision.")
def release_rollback(release_id: str, environment: str, window: str, reason: str) -> None:
    """Roll back to a prior release (audit record + promoted pointer update)."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    target = storage.get_release(release_id)
    if not target:
        raise click.ClickException(f"Unknown release: {release_id}")

    target_artifact = ReleaseArtifact.model_validate(target.artifact_json)
    agent_id = target_artifact.spec.agent.agent_id
    active_policy = storage.get_active_policy() or default_policy()
    current_release_id = storage.get_promoted_release_id(agent_id, environment)
    if not current_release_id:
        raise click.ClickException("No promoted release exists for this agent/environment; nothing to roll back to.")

    baseline = storage.get_release(current_release_id)
    if not baseline:
        raise click.ClickException(f"Promoted baseline release is missing: {current_release_id}")

    baseline_artifact = ReleaseArtifact.model_validate(baseline.artifact_json)
    baseline_pricing_ref = baseline_artifact.spec.pricing_reference
    candidate_pricing_ref = target_artifact.spec.pricing_reference

    baseline_table = storage.get_pricing_table(baseline_pricing_ref.provider, baseline_pricing_ref.pricing_version)
    if not baseline_table:
        raise click.ClickException(
            "Missing pricing table for promoted baseline "
            f"{baseline_pricing_ref.provider}/{baseline_pricing_ref.pricing_version}. "
            "Run `flightdeck pricing import ...`."
        )

    candidate_table = storage.get_pricing_table(candidate_pricing_ref.provider, candidate_pricing_ref.pricing_version)
    if not candidate_table:
        raise click.ClickException(
            "Missing pricing table for rollback target "
            f"{candidate_pricing_ref.provider}/{candidate_pricing_ref.pricing_version}. "
            "Run `flightdeck pricing import ...`."
        )

    try:
        delta = parse_window(window)
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    until = utc_now()
    since = until - delta

    baseline_events = storage.query_runs(
        current_release_id,
        since,
        until,
        environment=environment,
    )
    candidate_events = storage.query_runs(
        release_id,
        since,
        until,
        environment=environment,
    )

    try:
        diff = diff_releases(
            cfg=cfg,
            policy=active_policy,
            baseline_events=baseline_events,
            candidate_events=candidate_events,
            baseline_pricing_table=baseline_table,
            candidate_pricing_table=candidate_table,
            window=window,
        )
    except KeyError as e:
        raise click.ClickException(
            "Pricing table missing model entry. "
            f"baseline_model={baseline_artifact.spec.runtime.model} "
            f"candidate_model={target_artifact.spec.runtime.model}."
        ) from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    policy_result = diff.policy

    record = PromotionRecord(
        action_id=f"act_{uuid4().hex[:12]}",
        action="rollback",
        actor=actor_name(),
        release_id=release_id,
        agent_id=agent_id,
        environment=environment,
        reason=reason,
        policy_result=policy_result,
        baseline_release_id=current_release_id,
        created_at=utc_now(),
    )

    if not policy_result.passed:
        storage.insert_promotion_record(record)
        click.echo("Policy: FAIL")
        for r in policy_result.reasons:
            click.echo(f"- {r}")
        raise click.ClickException("Rollback blocked by policy")

    storage.commit_promotion(record, new_promoted_release_id=release_id)
    click.echo(f"Rolled back to {release_id} for {agent_id}/{environment}")
    click.echo("Policy: PASS")
    for r in policy_result.reasons:
        click.echo(f"- {r}")


@release.command("history")
@click.option("--agent", "agent_id", default=None)
@click.option("--env", "environment", default=None)
def release_history(agent_id: str | None, environment: str | None) -> None:
    """Show release promotion decision history."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()

    records = storage.list_release_actions(agent_id=agent_id, environment=environment)
    for r in records:
        status = "PASS" if r.policy_result.passed else "FAIL"
        baseline = r.baseline_release_id or "-"
        click.echo(
            f"{r.created_at.isoformat()}\t{r.action}\t{status}\t"
            f"{r.release_id}\tbaseline={baseline}\tactor={r.actor}\treason={r.reason}"
        )
        for reason_text in r.policy_result.reasons:
            click.echo(f"  - {reason_text}")


if __name__ == "__main__":
    cli()
