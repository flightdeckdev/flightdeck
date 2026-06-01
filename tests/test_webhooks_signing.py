from __future__ import annotations

import hashlib
import hmac
import json

from flightdeck.webhooks import (
    EVENT_TYPES,
    build_event_payload,
    generate_secret,
    sign_payload,
)


def test_event_types_contains_v1_events() -> None:
    assert "promote.succeeded" in EVENT_TYPES
    assert "rollback.succeeded" in EVENT_TYPES
    assert "promote.blocked" in EVENT_TYPES


def test_generate_secret_returns_url_safe_high_entropy_string() -> None:
    a = generate_secret()
    b = generate_secret()
    assert a != b
    # token_urlsafe(32) → base64 of 32 random bytes ~= 43 chars (no padding).
    assert len(a) >= 40
    # URL-safe alphabet only.
    assert all(c.isalnum() or c in "-_" for c in a)


def test_sign_payload_matches_known_answer() -> None:
    secret = "shhh"  # noqa: S105 — fixture secret for KAT
    body = b'{"event":"promote.succeeded","x":1}'
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert sign_payload(secret, body) == expected


def test_sign_payload_changes_with_body() -> None:
    secret = "shhh"  # noqa: S105
    a = sign_payload(secret, b"a")
    b = sign_payload(secret, b"b")
    assert a != b
    assert a.startswith("sha256=") and b.startswith("sha256=")


def test_sign_payload_changes_with_secret() -> None:
    body = b"hello"
    a = sign_payload("k1", body)
    b = sign_payload("k2", body)
    assert a != b


def test_build_event_payload_envelope() -> None:
    payload = build_event_payload("promote.succeeded", {"release_id": "rel_1"})
    assert payload["event"] == "promote.succeeded"
    assert payload["data"] == {"release_id": "rel_1"}
    assert isinstance(payload["delivery_id"], str) and len(payload["delivery_id"]) >= 16
    assert isinstance(payload["created_at"], str)
    # Round-trip through json so callers can rely on JSON-safety.
    assert json.loads(json.dumps(payload)) == payload


def test_build_event_payload_unique_delivery_ids() -> None:
    p1 = build_event_payload("x", {})
    p2 = build_event_payload("x", {})
    assert p1["delivery_id"] != p2["delivery_id"]
