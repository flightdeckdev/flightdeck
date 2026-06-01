"""HMAC-signed outbound webhooks for promote/rollback events.

v1 design (deliberate constraints):

- Synchronous fan-out inside the request handler (no queue, no thread pool).
- 5 s per-request timeout, 3 attempts with exponential backoff (1 s, 2 s, 4 s).
- Per-webhook ``secret`` (URL-safe base64, 32 bytes of entropy) signs the raw
  request body with HMAC-SHA256, mirrored on the receiver as the GitHub convention.
- Delivery failures are **logged**, never raised — webhook fan-out must never
  break a promote / rollback / policy-block path.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any
from uuid import uuid4

import httpx

from flightdeck.models import utc_now
from flightdeck.storage import Storage

logger = logging.getLogger(__name__)


EVENT_TYPES: frozenset[str] = frozenset(
    {
        "promote.succeeded",
        "rollback.succeeded",
        "promote.blocked",
    }
)


def generate_secret() -> str:
    """Return a URL-safe base64 secret (32 bytes of entropy)."""
    return secrets.token_urlsafe(32)


def sign_payload(secret: str, body: bytes) -> str:
    """Return the ``sha256=<hex>`` signature header value for ``body``."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_event_payload(event: str, data: dict[str, Any]) -> dict[str, Any]:
    """Wrap an event-specific ``data`` dict in the standard envelope."""
    return {
        "event": event,
        "delivery_id": uuid4().hex,
        "created_at": utc_now().isoformat(),
        "data": data,
    }


def _deliver_one(
    client: httpx.Client,
    *,
    webhook_id: str,
    url: str,
    secret: str,
    event: str,
    body: bytes,
    delivery_id: str,
    max_attempts: int,
) -> dict[str, Any]:
    """Synchronous best-effort delivery with bounded exponential backoff."""
    signature = sign_payload(secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-FlightDeck-Signature": signature,
        "X-FlightDeck-Event": event,
        "X-FlightDeck-Delivery": delivery_id,
        "User-Agent": "FlightDeck-Webhook/1",
    }
    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.post(url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Webhook delivery transport error: webhook_id=%s attempt=%d/%d url=%s error=%s",
                webhook_id,
                attempt,
                max_attempts,
                url,
                last_error,
            )
        else:
            if 200 <= resp.status_code < 300:
                return {
                    "webhook_id": webhook_id,
                    "status": "delivered",
                    "attempts": attempt,
                    "http_status": resp.status_code,
                    "error": None,
                }
            last_error = f"HTTP {resp.status_code}"
            logger.warning(
                "Webhook non-2xx response: webhook_id=%s attempt=%d/%d url=%s status=%d",
                webhook_id,
                attempt,
                max_attempts,
                url,
                resp.status_code,
            )
        if attempt < max_attempts:
            backoff = 2 ** (attempt - 1)  # 1 s, 2 s, 4 s, ...
            time.sleep(backoff)
    return {
        "webhook_id": webhook_id,
        "status": "failed",
        "attempts": max_attempts,
        "http_status": None,
        "error": last_error,
    }


def dispatch_event(
    storage: Storage,
    event: str,
    data: dict[str, Any],
    *,
    timeout: float = 5.0,
    max_attempts: int = 3,
) -> list[dict[str, Any]]:
    """Fan-out an event payload to every enabled webhook subscribed to ``event``.

    Returns a list of per-webhook delivery results for observability. Never raises:
    transport, timeout, and non-2xx responses are logged and surfaced in the result
    dicts only.
    """
    try:
        rows = storage.list_webhooks(enabled_only=True)
    except Exception:
        logger.warning("Webhook dispatch: list_webhooks failed", exc_info=True)
        return []

    subscribed = [row for row in rows if event in (row.get("events") or [])]
    if not subscribed:
        return []

    payload = build_event_payload(event, data)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    delivery_id = payload["delivery_id"]

    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            for row in subscribed:
                try:
                    results.append(
                        _deliver_one(
                            client,
                            webhook_id=str(row["webhook_id"]),
                            url=str(row["url"]),
                            secret=str(row["secret"]),
                            event=event,
                            body=body,
                            delivery_id=delivery_id,
                            max_attempts=max_attempts,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "Webhook dispatch: unexpected error for webhook_id=%s: %s",
                        row.get("webhook_id"),
                        exc,
                        exc_info=True,
                    )
                    results.append(
                        {
                            "webhook_id": str(row.get("webhook_id")),
                            "status": "failed",
                            "attempts": 0,
                            "http_status": None,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
    except Exception:
        logger.warning("Webhook dispatch: httpx client failed", exc_info=True)
    return results
