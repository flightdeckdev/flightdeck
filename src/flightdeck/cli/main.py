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
from flightdeck.models import (
    Policy,
    PricingTable,
    ReleaseArtifact,
    ReleaseRecord,
    RunEvent,
    utc_now,
)
from flightdeck.operations import (
    OperationError,
    compute_diff,
    confirm_promotion_request,
    default_policy,
    diff_outcome_to_public_dict,
    promote_release,
    query_run_events_page,
    request_promotion,
    rollback_release,
)
from flightdeck.storage import Storage


def read_release_artifact(path: Path) -> ReleaseArtifact:
    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    return ReleaseArtifact.model_validate(data)


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
@click.option(
    "--backup",
    "backup_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Copy the workspace SQLite database to PATH (online backup), then run checks.",
)
def doctor_cmd(backup_path: Path | None) -> None:
    """Run read-only health checks on the local ledger (migrations, promoted pointers)."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    if backup_path is not None:
        storage.backup_to(backup_path)
        click.echo(f"Backed up database to {backup_path}")
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
    """Start the local FlightDeck HTTP service (ingest + local release operations)."""
    import uvicorn

    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    if host.strip() not in loopback_hosts:
        click.echo(
            f"Warning: binding to {host!r} may expose local ingest/action endpoints; "
            "use trusted networks and set a local API token when needed.",
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


@runs.command("list")
@click.argument("release_id")
@click.option("--window", required=True, help="Time window like 7d, 24h, 30m.")
@click.option("--env", "environment", default=None)
@click.option("--tenant", "tenant_id", default=None)
@click.option("--task", "task_id", default=None)
@click.option("--limit", default=100, show_default=True, type=int)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def runs_list(
    release_id: str,
    window: str,
    environment: str | None,
    tenant_id: str | None,
    task_id: str | None,
    limit: int,
    output_format: str,
) -> None:
    """List ingested run events for a release (newest first; truncated to --limit)."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()
    try:
        payload = query_run_events_page(
            cfg=cfg,
            storage=storage,
            release_id=release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
            limit=limit,
        )
    except OperationError as e:
        raise click.ClickException(str(e)) from e
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(
        f"release={payload['release_id']} matched_total={payload['matched_total']} "
        f"returned={payload['returned']} truncated={payload['truncated']}"
    )
    for ev in payload["events"]:
        click.echo(json.dumps(ev, sort_keys=True))


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
@click.option(
    "--fail-on-policy",
    is_flag=True,
    default=False,
    help="Exit with code 1 when the active policy does not pass (after printing the diff).",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format. 'json' emits the same shape as POST /v1/diff for machine consumers.",
)
def release_diff(
    baseline_release_id: str,
    candidate_release_id: str,
    window: str,
    tenant_id: str | None,
    task_id: str | None,
    environment: str | None,
    fail_on_policy: bool,
    output_format: str,
) -> None:
    """Compare two releases over a time window and print a confidence-labeled safety diff."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()
    try:
        result = compute_diff(
            cfg=cfg,
            storage=storage,
            baseline_release_id=baseline_release_id,
            candidate_release_id=candidate_release_id,
            window=window,
            environment=environment,
            tenant_id=tenant_id,
            task_id=task_id,
        )
    except OperationError as e:
        raise click.ClickException(str(e)) from e

    if output_format == "json":
        body = diff_outcome_to_public_dict(result)
        click.echo(json.dumps(body, indent=2, sort_keys=True))
        if fail_on_policy and not result.policy.passed:
            raise click.ClickException("Policy gate: diff blocked by active policy (see policy.reasons in JSON output).")
        return

    click.echo(f"Window: {window} ({result.since.isoformat()} .. {result.until.isoformat()})")
    click.echo(f"Filters: env={result.environment} tenant={tenant_id or '*'} task={task_id or '*'}")
    click.echo(
        f"Baseline pricing: {result.baseline_pricing_provider}/{result.baseline_pricing_version} "
        f"(model={result.baseline_model})"
    )
    click.echo(
        f"Candidate pricing: {result.candidate_pricing_provider}/{result.candidate_pricing_version} "
        f"(model={result.candidate_model})"
    )
    for w in result.pricing_warnings:
        click.echo(f"WARNING: {w}")
    for h in result.pricing_hints:
        click.echo(f"HINT: {h}")
    if result.catalog_enabled or result.catalog_warnings:
        click.echo(
            f"Catalog: enabled={result.catalog_enabled} version={result.catalog_version or '-'} "
            f"slots baseline={result.baseline_catalog_slot_id or '-'} candidate={result.candidate_catalog_slot_id or '-'}"
        )
        if (
            result.baseline_catalog_cost_per_run_usd is not None
            and result.candidate_catalog_cost_per_run_usd is not None
            and result.delta_catalog_cost_per_run_usd is not None
        ):
            click.echo(
                f"Catalog-comparable cost/run (USD): {result.baseline_catalog_cost_per_run_usd:.6f} -> "
                f"{result.candidate_catalog_cost_per_run_usd:.6f} "
                f"(delta {result.delta_catalog_cost_per_run_usd:+.6f})"
            )
        for cw in result.catalog_warnings:
            click.echo(f"WARNING (catalog): {cw}")
    if result.pricing_or_model_changed:
        click.echo("NOTE: cost delta includes pricing/model assumption changes (pricing reference and/or model differ).")
        if (
            result.baseline_input_usd_per_1k_tokens is not None
            and result.candidate_input_usd_per_1k_tokens is not None
            and result.baseline_output_usd_per_1k_tokens is not None
            and result.candidate_output_usd_per_1k_tokens is not None
        ):
            click.echo(
                "Per-1k token prices: "
                f"input {result.baseline_input_usd_per_1k_tokens:.6f} -> "
                f"{result.candidate_input_usd_per_1k_tokens:.6f}, "
                f"output {result.baseline_output_usd_per_1k_tokens:.6f} -> "
                f"{result.candidate_output_usd_per_1k_tokens:.6f}"
            )
    click.echo(f"Samples: baseline={result.baseline_runs} candidate={result.candidate_runs}")
    click.echo(
        f"Confidence: {result.confidence}" + (f" ({result.confidence_reason})" if result.confidence_reason else "")
    )
    click.echo("")
    click.echo(
        f"Estimated model token cost/run (USD): {result.baseline_cost_per_run_usd:.6f} -> "
        f"{result.candidate_cost_per_run_usd:.6f} (delta {result.delta_cost_per_run_usd:+.6f}"
        + (f", {result.delta_cost_per_run_pct:+.2%})" if result.delta_cost_per_run_pct is not None else ")")
    )
    if result.baseline_latency_ms_avg is not None and result.candidate_latency_ms_avg is not None:
        click.echo(
            f"Latency avg (ms): {result.baseline_latency_ms_avg:.2f} -> {result.candidate_latency_ms_avg:.2f} "
            f"(delta {result.delta_latency_ms_avg:+.2f})"
        )
    click.echo(
        f"Error rate: {result.baseline_error_rate:.4f} -> {result.candidate_error_rate:.4f} "
        f"(delta {result.delta_error_rate:+.4f})"
    )
    click.echo("")
    click.echo("Policy: " + ("PASS" if result.policy.passed else "FAIL"))
    for r in result.policy.reasons:
        click.echo(f"- {r}")
    if fail_on_policy and not result.policy.passed:
        raise click.ClickException("Policy gate: diff blocked by active policy (see reasons above).")


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
    try:
        outcome = promote_release(
            cfg=cfg,
            storage=storage,
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor_name(),
        )
    except OperationError as e:
        raise click.ClickException(str(e)) from e

    if not outcome.policy.passed:
        click.echo("Policy: FAIL")
        for r in outcome.policy.reasons:
            click.echo(f"- {r}")
        raise click.ClickException("Promotion blocked by policy")

    click.echo(f"Promoted {release_id} for {outcome.agent_id}/{environment}")
    click.echo("Policy: PASS")
    for r in outcome.policy.reasons:
        click.echo(f"- {r}")


@release.command("promote-request")
@click.argument("release_id")
@click.option("--env", "environment", required=True)
@click.option("--window", required=True, help="Required. Time window like 7d, 24h, 30m.")
@click.option("--reason", required=True, help="Rationale for requesting promotion (policy must pass).")
def release_promote_request(release_id: str, environment: str, window: str, reason: str) -> None:
    """Create a pending promotion request (requires promotion_requires_approval in flightdeck.yaml)."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()
    try:
        record = request_promotion(
            cfg=cfg,
            storage=storage,
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor_name(),
        )
    except OperationError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"request_id={record.request_id}")
    click.echo(json.dumps({"policy": record.policy_result.model_dump(mode="json")}, indent=2))


@release.command("promote-confirm")
@click.argument("request_id")
@click.option("--approval-reason", required=True, help="Human approval rationale.")
def release_promote_confirm(request_id: str, approval_reason: str) -> None:
    """Confirm a pending promotion request and perform the promotion."""
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.migrate()
    try:
        outcome = confirm_promotion_request(
            cfg=cfg,
            storage=storage,
            request_id=request_id,
            approval_reason=approval_reason,
            actor=actor_name(),
        )
    except OperationError as e:
        raise click.ClickException(str(e)) from e

    if not outcome.policy.passed:
        click.echo("Policy: FAIL")
        for r in outcome.policy.reasons:
            click.echo(f"- {r}")
        raise click.ClickException("Promotion blocked by policy")

    click.echo(f"Promoted {outcome.release_id} for {outcome.agent_id}/{outcome.environment}")
    click.echo(f"action_id={outcome.action_id}")
    click.echo("Policy: PASS")
    for r in outcome.policy.reasons:
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
    try:
        outcome = rollback_release(
            cfg=cfg,
            storage=storage,
            release_id=release_id,
            environment=environment,
            window=window,
            reason=reason,
            actor=actor_name(),
        )
    except OperationError as e:
        raise click.ClickException(str(e)) from e

    if not outcome.policy.passed:
        click.echo("Policy: FAIL")
        for r in outcome.policy.reasons:
            click.echo(f"- {r}")
        raise click.ClickException("Rollback blocked by policy")

    click.echo(f"Rolled back to {release_id} for {outcome.agent_id}/{environment}")
    click.echo("Policy: PASS")
    for r in outcome.policy.reasons:
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
