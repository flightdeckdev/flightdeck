from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DiffConfig(BaseModel):
    min_candidate_runs: int = 500
    min_baseline_runs: int = 500
    min_low_runs: int = 50


class WorkspaceConfig(BaseModel):
    api_version: Literal["v1"] = "v1"
    kind: Literal["WorkspaceConfig"] = "WorkspaceConfig"

    db_path: str = ".flightdeck/flightdeck.db"
    # When set (``postgresql://`` or ``postgres://``), the ledger uses PostgreSQL instead of
    # the SQLite file at ``db_path``. Requires optional dependency ``psycopg`` (``--extra postgres``).
    database_url: str | None = None
    default_environment: str = "local"

    diff: DiffConfig = Field(default_factory=DiffConfig)

    # Optional path (relative to cwd or absolute) to a PricingCatalog YAML for
    # cross-vendor comparable per-run costs on diffs (additive ``pricing.catalog``).
    pricing_catalog_path: str | None = None

    # When true, ``POST /v1/promote`` and CLI ``release promote`` reject until a
    # pending request is confirmed (``promote/request`` + ``promote/confirm``).
    promotion_requires_approval: bool = False


class WorkspacePublic(BaseModel):
    """Read-only workspace flags for ``GET /v1/workspace`` (no secrets, no full YAML)."""

    api_version: Literal["v1"] = "v1"
    kind: Literal["WorkspacePublic"] = "WorkspacePublic"
    promotion_requires_approval: bool
    pricing_catalog_configured: bool
    server_version: str

    @classmethod
    def from_workspace_config(cls, cfg: WorkspaceConfig, *, server_version: str) -> WorkspacePublic:
        path = (cfg.pricing_catalog_path or "").strip()
        return cls(
            promotion_requires_approval=cfg.promotion_requires_approval,
            pricing_catalog_configured=bool(path),
            server_version=server_version,
        )


class PricingEntry(BaseModel):
    model: str
    input_usd_per_1k_tokens: float = Field(ge=0)
    output_usd_per_1k_tokens: float = Field(ge=0)
    cached_input_usd_per_1k_tokens: float | None = Field(default=None, ge=0)


class PricingTable(BaseModel):
    provider: str
    pricing_version: str
    entries: list[PricingEntry]


class ReleasePricingReference(BaseModel):
    provider: str
    pricing_version: str


class ReleaseMetadata(BaseModel):
    name: str
    version: str
    description: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class ReleaseSpecAgent(BaseModel):
    agent_id: str
    entrypoint: str | None = None


class ReleaseSpecRuntime(BaseModel):
    provider: str
    model: str
    temperature: float | None = None
    max_output_tokens: int | None = None


class ReleaseSpecPrompts(BaseModel):
    system_ref: str
    template_refs: list[str] = Field(default_factory=list)


class ReleaseSpecTools(BaseModel):
    manifest_ref: str | None = None
    tool_names: list[str] = Field(default_factory=list)


class ReleaseSpecRoutingFallback(BaseModel):
    model: str
    on_error: bool = True


class ReleaseSpecRouting(BaseModel):
    strategy: Literal["single_model", "fallback_model"] = "single_model"
    fallback: ReleaseSpecRoutingFallback | None = None


class ReleaseSpecSafetyRetryPolicy(BaseModel):
    max_retries: int = 0
    backoff_ms: int | None = None


class ReleaseSpecSafetyTimeouts(BaseModel):
    model_call: int | None = None
    tool_call: int | None = None


class ReleaseSpecSafety(BaseModel):
    retry_policy: ReleaseSpecSafetyRetryPolicy = Field(default_factory=ReleaseSpecSafetyRetryPolicy)
    timeouts_ms: ReleaseSpecSafetyTimeouts | None = None


class ReleaseSpec(BaseModel):
    agent: ReleaseSpecAgent
    runtime: ReleaseSpecRuntime
    prompts: ReleaseSpecPrompts
    tools: ReleaseSpecTools | None = None
    routing: ReleaseSpecRouting | None = None
    safety: ReleaseSpecSafety | None = None
    pricing_reference: ReleasePricingReference
    tags: dict[str, str] = Field(default_factory=dict)


class ReleaseArtifact(BaseModel):
    api_version: Literal["v1"] = "v1"
    kind: Literal["Release"] = "Release"
    metadata: ReleaseMetadata
    spec: ReleaseSpec


class RunEventRequest(BaseModel):
    session_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None


class RunEventMetrics(BaseModel):
    latency_ms: int | None = Field(default=None, ge=0)
    success: bool = True
    error_type: str | None = None


class RunEventModelUsage(BaseModel):
    provider: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)


class RunEventToolUsage(BaseModel):
    tool_name: str
    invocations: int = Field(default=0, ge=0)
    cost_units: float = Field(default=0.0, ge=0)


class RunEventUsage(BaseModel):
    model: RunEventModelUsage
    tools: list[RunEventToolUsage] = Field(default_factory=list)


class RunEvent(BaseModel):
    api_version: Literal["v1"] = "v1"
    type: Literal["run_start", "run_end"] = "run_end"
    timestamp: datetime

    workspace_id: str = "ws_local"
    agent_id: str
    release_id: str
    run_id: str

    tenant_id: str
    task_id: str
    environment: str

    request: RunEventRequest | None = None
    metrics: RunEventMetrics = Field(default_factory=RunEventMetrics)
    usage: RunEventUsage
    labels: dict[str, str] = Field(default_factory=dict)


class Policy(BaseModel):
    """Promotion-gate policy for a release diff.

    **Constraint fields** (``max_*``) — when ``None`` the constraint is
    disabled.  When set, the candidate rollup must not exceed the limit for the
    policy to pass.

    **Sample threshold fields** (``min_*``) — control the confidence label
    assigned by ``diff_releases``:

    - ``None`` (default) — defer to ``WorkspaceConfig.diff`` defaults
      (typically ``min_candidate_runs=500``, ``min_baseline_runs=500``,
      ``min_low_runs=50``).
    - ``0`` — unconditionally accept any sample size for that threshold,
      including an empty event list.  All three set to ``0`` means any diff
      window, even an empty one, can reach HIGH confidence.

    The ``None`` / ``0`` distinction is intentional: ``None`` means "inherit
    from config", not "zero runs required".  ``diff_releases`` uses
    ``is not None`` checks to respect an explicit ``0`` override.
    """

    policy_id: str = "default"
    max_cost_per_run_usd: float | None = Field(default=None, ge=0)
    max_latency_ms: int | None = Field(default=None, ge=0)
    max_error_rate: float | None = Field(default=None, ge=0, le=1)

    min_candidate_runs: int | None = Field(default=None, ge=0)
    min_baseline_runs: int | None = Field(default=None, ge=0)
    min_low_runs: int | None = Field(default=None, ge=0)

    # When true, promotion decisions require HIGH diff confidence (not just threshold deltas).
    require_high_diff_confidence: bool = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyResult(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utc_now)


class ReleaseRecord(BaseModel):
    release_id: str
    agent_id: str
    version: str
    environment: str
    checksum: str
    artifact_json: dict[str, Any]
    created_at: datetime


class PromotionRecord(BaseModel):
    action_id: str
    action: Literal["promote", "rollback"]
    actor: str
    release_id: str
    agent_id: str
    environment: str
    reason: str
    policy_result: PolicyResult
    baseline_release_id: str | None = None
    created_at: datetime
    # Assigned by storage on insert when None; monotonic for `flightdeck doctor` gap checks.
    audit_seq: int | None = None


class PromotionRequestRecord(BaseModel):
    """Pending human approval before ``commit_promotion``."""

    request_id: str
    status: Literal["pending", "completed", "cancelled"] = "pending"
    release_id: str
    agent_id: str
    environment: str
    window: str
    reason: str
    actor: str
    baseline_release_id: str | None = None
    policy_result: PolicyResult
    created_at: datetime
    resolved_at: datetime | None = None
    completed_action_id: str | None = None


class WebhookCreate(BaseModel):
    """Create-request body for ``POST /v1/webhooks``."""

    url: str = Field(min_length=1)
    events: list[str] = Field(min_length=1)
    description: str | None = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        # Defence-in-depth against SSRF (reviewer MAJOR-7). An operator with
        # ledger-write access can register a webhook URL; that URL receives
        # every promote / rollback payload. Without validation, a careless
        # or malicious entry could point at a cloud metadata service (AWS
        # IMDS, GCP metadata, Azure IMDS) and either fan out audit data to
        # a host the operator did not intend, or probe the host file system
        # via file:// URLs.
        #
        # This validator enforces the minimum:
        #   - scheme must be http or https (no file://, gopher://, ftp://, ...)
        #   - link-local IPv4 + IPv6 are rejected (covers all standard cloud
        #     metadata endpoints: 169.254.169.254 / fe80::/10)
        #   - a small allowlist of known-metadata hostnames is rejected
        # Private RFC1918 and loopback are intentionally allowed (FlightDeck
        # is local-first and self-hosted Slack / Discord receivers commonly
        # live on private nets). HTTP scheme is allowed but operators should
        # use HTTPS in production.
        #
        # Test coverage lives in ``tests/test_webhooks_url_validation.py``.
        from urllib.parse import urlparse
        import ipaddress

        try:
            parsed = urlparse(value)
        except ValueError as exc:
            raise ValueError(f"Invalid webhook URL: {exc}") from exc

        scheme = (parsed.scheme or "").lower()
        if scheme not in {"http", "https"}:
            raise ValueError(
                f"Webhook URL scheme must be http or https (got {scheme!r})."
            )
        host = (parsed.hostname or "").strip().lower()
        if not host:
            raise ValueError("Webhook URL must include a host.")

        _METADATA_HOSTNAMES = {
            "metadata.google.internal",
            "metadata",
            "instance-data",
            "instance-data.ec2.internal",
        }
        if host in _METADATA_HOSTNAMES:
            raise ValueError(
                "Webhook URL targets a cloud-metadata hostname; refusing to register."
            )

        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip is not None and ip.is_link_local:
            # Catches IPv4 169.254.0.0/16 (AWS IMDS 169.254.169.254, ECS
            # 169.254.170.2) and IPv6 fe80::/10 in one check.
            raise ValueError(
                "Webhook URL targets a link-local address (cloud-metadata range); refusing."
            )
        return value

    @field_validator("events")
    @classmethod
    def _validate_events(cls, value: list[str]) -> list[str]:
        # Import inside validator to avoid a circular import at module load.
        from flightdeck.webhooks import EVENT_TYPES

        bad = [e for e in value if e not in EVENT_TYPES]
        if bad:
            raise ValueError(
                f"Unsupported event(s): {sorted(set(bad))}. Allowed: {sorted(EVENT_TYPES)}"
            )
        return value


class WebhookPublic(BaseModel):
    """Wire shape for ``POST /v1/webhooks`` (with ``secret``) and ``GET /v1/webhooks`` (with ``secret_preview``)."""

    api_version: Literal["v1"] = "v1"
    kind: Literal["Webhook"] = "Webhook"
    webhook_id: str
    url: str
    events: list[str]
    enabled: bool
    created_at: str
    description: str | None = None
    # ``secret`` is populated only on the create response (the one and only time the
    # caller sees the cleartext). ``secret_preview`` is populated only on list.
    secret: str | None = None
    secret_preview: str | None = None


class WebhookListResponse(BaseModel):
    api_version: Literal["v1"] = "v1"
    kind: Literal["WebhookList"] = "WebhookList"
    webhooks: list[WebhookPublic]
    total: int
