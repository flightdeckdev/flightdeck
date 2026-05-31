"""FlightDeck CLI — release diffs, runtime evidence, policy gates."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import click
import yaml
from click.exceptions import Exit as ClickExit

from flightdeck import __version__
from flightdeck.bundle import bundle_checksum
from flightdeck.demo_flow import demo_session
from flightdeck.bundled_pricing_bootstrap import (
    BUNDLED_PRICING_VERSION,
    DEFAULT_CATALOG_RELATIVE_PATH,
    bootstrap_bundled_pricing,
)
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
from flightdeck.storage import storage_from_config


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
    """Ship AI agents safely — release diffs, runtime evidence, policy gates."""


@cli.command("version")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON (for CI scripts, chatops bots, dashboards).",
)
def version_cmd(as_json: bool) -> None:
    """Print the FlightDeck version (default: human; --json: machine-readable)."""
    if as_json:
        import json

        click.echo(json.dumps({"name": "flightdeck-ai", "version": __version__}))
    else:
        click.echo(f"flightdeck {__version__}")


@cli.command()
@click.option("--path", "path_", default=DEFAULT_CONFIG_FILENAME, show_default=True)
@click.option(
    "--no-bundled-pricing",
    is_flag=True,
    default=False,
    help="Skip bundled OpenAI/Anthropic/Google pricing import and catalog (air-gapped or custom-only).",
)
def init(path_: str, no_bundled_pricing: bool) -> None:
    """Create a local `flightdeck.yaml` workspace config."""
    p = Path(path_)
    if p.exists():
        raise click.ClickException(f"{p} already exists")
    catalog_rel: str | None = None if no_bundled_pricing else DEFAULT_CATALOG_RELATIVE_PATH
    written = write_default_config(p, pricing_catalog_path=catalog_rel)
    click.echo(f"Wrote {written}")
    cfg = load_config(written)
    storage = storage_from_config(cfg)
    storage.migrate()
    if not no_bundled_pricing:
        rel = cfg.pricing_catalog_path or DEFAULT_CATALOG_RELATIVE_PATH
        catalog_dest = (Path.cwd() / Path(rel)).resolve()
        bootstrap_bundled_pricing(storage=storage, actor=actor_name(), catalog_dest=catalog_dest)
        click.echo(
            f"Bundled pricing snapshot ({BUNDLED_PRICING_VERSION}): imported openai, anthropic, google; "
            f"wrote catalog to {rel}"
        )


@cli.command()
@click.option(
    "--quickstart-root",
    "quickstart_root_opt",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Directory with quickstart YAML/JSONL fixtures (default: repo examples/ or bundled wheel copy).",
)
@click.option(
    "--verify/--no-verify",
    default=False,
    show_default=True,
    help="Also run release verify on the baseline bundle (matches flightdeck-quickstart-verify).",
)
@click.option(
    "--doctor/--no-doctor",
    default=False,
    show_default=True,
    help="Also run flightdeck doctor after the workflow.",
)
@click.option(
    "--keep-workspace",
    is_flag=True,
    default=False,
    help="Keep the temp workspace and print its path (for inspection).",
)
def demo(
    quickstart_root_opt: Path | None,
    verify: bool,
    doctor: bool,
    keep_workspace: bool,
) -> None:
    """Run the bundled quickstart end-to-end in a disposable workspace (no manual sed).

    Typical install: ``pip install flightdeck-ai`` then ``flightdeck demo``. Next: ``flightdeck init``
    in your project and wire ``runs ingest`` / ``release diff`` from real agents.
    """
    ws = demo_session(
        verify=verify,
        doctor=doctor,
        qs_dir=str(quickstart_root_opt) if quickstart_root_opt is not None else None,
        promote_reason="demo",
        keep_workspace=keep_workspace,
    )
    click.echo(
        "Demo OK — workspace initialized, releases registered, runs ingested, "
        "diff computed, baseline promoted under policy."
    )
    extras = []
    if verify:
        extras.append("verify")
    if doctor:
        extras.append("doctor")
    if extras:
        click.echo(f"(also ran: {', '.join(extras)})")
    if keep_workspace and ws is not None:
        click.echo(f"Workspace: {ws}")


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
    storage = storage_from_config(cfg)
    if backup_path is not None:
        try:
            storage.backup_to(backup_path)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
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
@click.option(
    "--sqlite-lock-timeout",
    type=float,
    default=30.0,
    show_default=True,
    help=(
        "Seconds to retry SQLite 'database is locked' / 'busy' errors on ledger statements "
        "(0 disables timed retries; PRAGMA busy_timeout still uses FLIGHTDECK_SQLITE_BUSY_TIMEOUT_MS)."
    ),
)
@click.option(
    "--retry-sqlite-lock/--no-retry-sqlite-lock",
    default=True,
    show_default=True,
    help="Retry SQLite locked/busy errors until --sqlite-lock-timeout elapses.",
)
def serve(
    host: str,
    port: int,
    reload: bool,
    sqlite_lock_timeout: float,
    retry_sqlite_lock: bool,
) -> None:
    """Start the local FlightDeck HTTP service (ingest + local release operations)."""
    import uvicorn

    os.environ["FLIGHTDECK_SQLITE_LOCK_TIMEOUT_S"] = str(sqlite_lock_timeout)
    os.environ["FLIGHTDECK_SQLITE_RETRY_ON_LOCK"] = "1" if retry_sqlite_lock else "0"

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
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
    storage.migrate()
    for r in storage.list_releases():
        click.echo(f"{r.release_id}\t{r.agent_id}\t{r.version}\t{r.environment}\t{r.created_at.isoformat()}")


@release.command("show")
@click.argument("release_id")
def release_show(release_id: str) -> None:
    """Show a registered release record as JSON."""
    cfg = load_config()
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
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
    """Import, inspect, and check staleness of pricing tables."""


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
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
    storage.migrate()

    table = storage.get_pricing_table(provider, pricing_version)
    if not table:
        raise click.ClickException(f"Pricing table not found: {provider}/{pricing_version}")
    click.echo(table.model_dump_json(indent=2))


@pricing.command("check")
@click.option(
    "--max-age-days",
    default=90,
    show_default=True,
    type=int,
    help="Warn when a bundled snapshot anchor is older than this many days.",
)
@click.option(
    "--fail",
    is_flag=True,
    default=False,
    help="Exit with code 1 if any bundled snapshot exceeds --max-age-days.",
)
def pricing_check(max_age_days: int, fail: bool) -> None:
    """Check age of ``flightdeck-bundled-*`` pricing tables in the ledger (UTC anchor month)."""
    from flightdeck.bundled_pricing_age import (
        bundled_pricing_age_days,
        bundled_pricing_anchor_date,
        is_flightdeck_bundled_pricing_version,
        pricing_stale_check_date,
    )

    if max_age_days < 0:
        raise click.ClickException("--max-age-days must be non-negative")

    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()

    today = pricing_stale_check_date()
    bundled = [
        v
        for v in storage.list_distinct_pricing_versions()
        if is_flightdeck_bundled_pricing_version(v)
    ]
    if not bundled:
        click.echo("No flightdeck-bundled-* pricing tables in the ledger.")
        return

    stale_any = False
    for v in bundled:
        anchor = bundled_pricing_anchor_date(v)
        age = bundled_pricing_age_days(v, today=today)
        assert anchor is not None and age is not None
        if age > max_age_days:
            stale_any = True
            click.echo(
                f"STALE  {v}  (anchor {anchor.isoformat()}, ~{age} days old; max {max_age_days})",
                err=True,
            )
        else:
            click.echo(f"OK     {v}  (~{age} days old; max {max_age_days})")

    if fail and stale_any:
        raise ClickExit(1)


@cli.group()
def policy() -> None:
    """Set and view promotion policy."""


@policy.command("set")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def policy_set(path: Path) -> None:
    """Set the active promotion policy from YAML."""
    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    p = Policy.model_validate(data)
    storage.set_active_policy(p)
    click.echo(f"Set policy {p.policy_id}")


@policy.command("show")
def policy_show() -> None:
    """Show the active promotion policy."""
    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()

    p = storage.get_active_policy() or default_policy()
    click.echo(p.model_dump_json(indent=2))


@cli.group()
def runs() -> None:
    """Ingest, list, and export run events."""


@runs.command("list")
@click.argument("release_id")
@click.option("--window", required=True, help="Time window like 7d, 24h, 30m.")
@click.option("--env", "environment", default=None)
@click.option("--tenant", "tenant_id", default=None)
@click.option("--task", "task_id", default=None)
@click.option("--trace-id", "trace_id", default=None, help="Filter to events whose request.trace_id matches (exact).")
@click.option("--session-id", "session_id", default=None, help="Filter to request.session_id (exact).")
@click.option("--span-id", "span_id", default=None, help="Filter to request.span_id (exact).")
@click.option("--offset", default=0, show_default=True, type=click.IntRange(0, 500_000))
@click.option("--limit", default=100, show_default=True, type=click.IntRange(1, 500))
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
    trace_id: str | None,
    session_id: str | None,
    span_id: str | None,
    offset: int,
    limit: int,
    output_format: str,
) -> None:
    """List ingested run events for a release (newest first; truncated to --limit)."""
    cfg = load_config()
    storage = storage_from_config(cfg)
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
            trace_id=trace_id,
            session_id=session_id,
            span_id=span_id,
            offset=offset,
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


@runs.command("export")
@click.argument("release_id")
@click.option("--window", required=True, help="Time window like 7d, 24h, 30m.")
@click.option("--env", "environment", default=None)
@click.option("--tenant", "tenant_id", default=None)
@click.option("--task", "task_id", default=None)
@click.option("--trace-id", "trace_id", default=None, help="Filter to events whose request.trace_id matches (exact).")
@click.option("--session-id", "session_id", default=None, help="Filter to request.session_id (exact).")
@click.option("--span-id", "span_id", default=None, help="Filter to request.span_id (exact).")
@click.option("--offset", default=0, show_default=True, type=click.IntRange(0, 500_000))
@click.option("--limit", default=500, show_default=True, type=click.IntRange(1, 500))
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write JSONL to this file; default is stdout.",
)
def runs_export(
    release_id: str,
    window: str,
    environment: str | None,
    tenant_id: str | None,
    task_id: str | None,
    trace_id: str | None,
    session_id: str | None,
    span_id: str | None,
    offset: int,
    limit: int,
    output_path: Path | None,
) -> None:
    """Export run events as JSONL (newest first), same filters as ``runs list`` (truncated to --limit, max 500)."""
    cfg = load_config()
    storage = storage_from_config(cfg)
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
            trace_id=trace_id,
            session_id=session_id,
            span_id=span_id,
            offset=offset,
            limit=limit,
        )
    except OperationError as e:
        raise click.ClickException(str(e)) from e
    stream = output_path.open("w", encoding="utf-8", newline="\n") if output_path else None
    try:
        out = stream or sys.stdout
        for ev in payload["events"]:
            out.write(json.dumps(ev, sort_keys=True) + "\n")
    finally:
        if stream is not None:
            stream.close()
    if payload["truncated"]:
        click.echo(
            f"WARNING: exported {payload['returned']} of {payload['matched_total']} matching events "
            f"(offset={payload['offset']}, --limit {limit}).",
            err=True,
        )


@runs.command("ingest")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def runs_ingest(path: Path) -> None:
    """Ingest RunEvent JSONL (or JSON array) into local storage."""
    cfg = load_config()
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
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
    storage = storage_from_config(cfg)
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


@cli.group()
def webhook() -> None:
    """Manage HMAC-signed outbound webhooks (Slack / Discord / PagerDuty / Linear …)."""


@webhook.command("add")
@click.option("--url", required=True, help="HTTPS endpoint (HTTP allowed for local dev only).")
@click.option(
    "--event",
    "events",
    multiple=True,
    required=True,
    help="Subscribed event name. Pass --event multiple times to subscribe to several.",
)
@click.option("--description", default=None, help="Free-form note shown in `webhook list`.")
def webhook_add(url: str, events: tuple[str, ...], description: str | None) -> None:
    """Create a webhook subscription and print the freshly generated secret."""
    from flightdeck.webhooks import EVENT_TYPES, generate_secret

    if not events:
        raise click.ClickException("at least one --event is required")
    bad = sorted({e for e in events if e not in EVENT_TYPES})
    if bad:
        allowed = ", ".join(sorted(EVENT_TYPES))
        raise click.ClickException(f"unknown event(s): {bad}. Allowed: {allowed}")

    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()

    webhook_id = f"wh_{uuid4().hex}"
    secret = generate_secret()
    created_at = utc_now().isoformat()
    storage.insert_webhook(
        webhook_id=webhook_id,
        url=url,
        events=list(events),
        secret=secret,
        description=description,
        created_at=created_at,
    )

    click.echo(f"Created webhook {webhook_id} for {url}")
    click.echo(f"  events: {', '.join(events)}")
    click.echo("")
    click.echo("!!! SAVE THIS SECRET — IT WILL NOT BE SHOWN AGAIN !!!")
    click.echo(f"  secret: {secret}")


@webhook.command("list")
def webhook_list() -> None:
    """List configured webhooks (secrets are redacted)."""
    from rich.console import Console
    from rich.table import Table

    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()

    rows = storage.list_webhooks(enabled_only=False)
    table = Table(title="FlightDeck webhooks")
    table.add_column("webhook_id", style="bold")
    table.add_column("url")
    table.add_column("events")
    table.add_column("enabled")
    table.add_column("created_at")
    table.add_column("secret_preview")
    table.add_column("description")
    for row in rows:
        secret = str(row["secret"])
        preview = f"{secret[:6]}…{secret[-4:]}" if len(secret) > 10 else "…"
        table.add_row(
            row["webhook_id"],
            row["url"],
            ", ".join(row["events"]),
            "yes" if row["enabled"] else "no",
            row["created_at"],
            preview,
            row.get("description") or "",
        )
    Console().print(table)


@webhook.command("remove")
@click.argument("webhook_id")
@click.option("--yes", "assume_yes", is_flag=True, default=False, help="Skip confirmation prompt.")
def webhook_remove(webhook_id: str, assume_yes: bool) -> None:
    """Delete a webhook subscription."""
    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()

    if not assume_yes:
        click.confirm(f"Delete webhook {webhook_id}?", abort=True)
    if not storage.delete_webhook(webhook_id):
        raise click.ClickException(f"unknown webhook: {webhook_id}")
    click.echo(f"Deleted {webhook_id}")


@webhook.command("test")
@click.argument("webhook_id")
def webhook_test(webhook_id: str) -> None:
    """Send a synthetic test.ping payload to the webhook URL using the same signing path."""
    import httpx

    from flightdeck.webhooks import build_event_payload, sign_payload

    cfg = load_config()
    storage = storage_from_config(cfg)
    storage.migrate()

    row = storage.get_webhook(webhook_id)
    if not row:
        raise click.ClickException(f"unknown webhook: {webhook_id}")

    payload = build_event_payload(
        "test.ping",
        {"webhook_id": webhook_id, "note": "synthetic ping from `flightdeck webhook test`"},
    )
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-FlightDeck-Signature": sign_payload(str(row["secret"]), body),
        "X-FlightDeck-Event": "test.ping",
        "X-FlightDeck-Delivery": str(payload["delivery_id"]),
        "User-Agent": "FlightDeck-Webhook/1",
    }
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False) as client:
            resp = client.post(str(row["url"]), content=body, headers=headers)
    except httpx.HTTPError as exc:
        raise click.ClickException(f"transport error: {type(exc).__name__}: {exc}") from exc

    snippet = resp.text[:200].replace("\n", " ")
    click.echo(f"HTTP {resp.status_code} from {row['url']}")
    click.echo(f"  body[:200]: {snippet}")


if __name__ == "__main__":
    cli()
