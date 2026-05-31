"""HTTP routes for managing outbound HMAC-signed webhooks.

Endpoints (all under ``/v1/webhooks``):

- ``POST /v1/webhooks`` — create. Returns ``WebhookPublic`` with the freshly generated
  ``secret`` (the *only* time the cleartext secret is returned).
- ``GET /v1/webhooks`` — list. Secrets are redacted to ``secret_preview``.
- ``DELETE /v1/webhooks/{webhook_id}`` — delete.

All routes share the existing ``require_ledger_write_access`` policy with promote /
rollback / events: loopback by default, Bearer-required when ``FLIGHTDECK_LOCAL_API_TOKEN``
is set.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from flightdeck.models import WebhookCreate, WebhookListResponse, WebhookPublic, utc_now
from flightdeck.server.mutation_access import require_ledger_write_access
from flightdeck.server.routes.common import ensure_app_state
from flightdeck.webhooks import generate_secret

router = APIRouter()


def _redact(secret: str) -> str:
    """Shape-preserving redaction for list views (never returns the cleartext)."""
    if len(secret) <= 10:
        return "…"
    return f"{secret[:6]}…{secret[-4:]}"


@router.post("/v1/webhooks")
def post_webhook(request: Request, req: WebhookCreate) -> dict[str, object]:
    require_ledger_write_access(request)
    _, storage = ensure_app_state(request)

    webhook_id = f"wh_{uuid4().hex}"
    secret = generate_secret()
    created_at = utc_now().isoformat()

    storage.insert_webhook(
        webhook_id=webhook_id,
        url=req.url,
        events=list(req.events),
        secret=secret,
        description=req.description,
        created_at=created_at,
    )

    public = WebhookPublic(
        webhook_id=webhook_id,
        url=req.url,
        events=list(req.events),
        enabled=True,
        created_at=created_at,
        description=req.description,
        secret=secret,
        secret_preview=None,
    )
    return public.model_dump(mode="json")


@router.get("/v1/webhooks")
def list_webhooks(request: Request) -> dict[str, object]:
    require_ledger_write_access(request)
    _, storage = ensure_app_state(request)
    rows = storage.list_webhooks(enabled_only=False)
    items = [
        WebhookPublic(
            webhook_id=row["webhook_id"],
            url=row["url"],
            events=list(row["events"]),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            description=row.get("description"),
            secret=None,
            secret_preview=_redact(row["secret"]),
        )
        for row in rows
    ]
    return WebhookListResponse(webhooks=items, total=len(items)).model_dump(mode="json")


@router.delete("/v1/webhooks/{webhook_id}")
def delete_webhook(request: Request, webhook_id: str) -> dict[str, object]:
    require_ledger_write_access(request)
    _, storage = ensure_app_state(request)
    if not storage.delete_webhook(webhook_id):
        raise HTTPException(status_code=404, detail=f"Unknown webhook: {webhook_id}")
    return {"webhook_id": webhook_id, "deleted": True}
