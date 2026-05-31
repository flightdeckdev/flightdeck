from __future__ import annotations

from pathlib import Path

from flightdeck.storage import LATEST_SCHEMA_MIGRATION_VERSION, Storage


def _storage(tmp_path: Path) -> Storage:
    s = Storage(str(tmp_path / "flightdeck.db"))
    s.migrate()
    return s


def test_migration_v5_applied(tmp_path: Path) -> None:
    s = _storage(tmp_path)
    versions = s.list_applied_migrations()
    assert 5 in versions
    assert LATEST_SCHEMA_MIGRATION_VERSION == 5


def test_migration_v5_is_idempotent(tmp_path: Path) -> None:
    s = _storage(tmp_path)
    s.migrate()
    s.migrate()
    versions = s.list_applied_migrations()
    assert versions.count(5) == 1


def test_insert_and_get_webhook_roundtrip(tmp_path: Path) -> None:
    s = _storage(tmp_path)
    s.insert_webhook(
        webhook_id="wh_test_1",
        url="https://hooks.example.com/foo",
        events=["promote.succeeded", "rollback.succeeded"],
        secret="topsecret-abcdef-123456",
        description="prod alerts",
        created_at="2026-05-31T00:00:00+00:00",
    )
    row = s.get_webhook("wh_test_1")
    assert row is not None
    assert row["webhook_id"] == "wh_test_1"
    assert row["url"] == "https://hooks.example.com/foo"
    assert row["events"] == ["promote.succeeded", "rollback.succeeded"]
    assert row["secret"] == "topsecret-abcdef-123456"
    assert row["enabled"] is True
    assert row["description"] == "prod alerts"
    assert row["created_at"] == "2026-05-31T00:00:00+00:00"


def test_get_missing_webhook_returns_none(tmp_path: Path) -> None:
    s = _storage(tmp_path)
    assert s.get_webhook("wh_does_not_exist") is None


def test_list_webhooks_returns_all_and_enabled_only(tmp_path: Path) -> None:
    s = _storage(tmp_path)
    s.insert_webhook(
        webhook_id="wh_a",
        url="https://a.example.com",
        events=["promote.succeeded"],
        secret="sa",
        description=None,
        created_at="2026-05-31T00:00:01+00:00",
    )
    s.insert_webhook(
        webhook_id="wh_b",
        url="https://b.example.com",
        events=["rollback.succeeded"],
        secret="sb",
        description=None,
        created_at="2026-05-31T00:00:02+00:00",
    )
    # Disable wh_a.
    with s.connect() as conn:
        conn.execute("UPDATE webhooks SET enabled = 0 WHERE webhook_id = ?", ("wh_a",))

    all_rows = s.list_webhooks(enabled_only=False)
    ids_all = {r["webhook_id"] for r in all_rows}
    assert ids_all == {"wh_a", "wh_b"}

    enabled_rows = s.list_webhooks(enabled_only=True)
    ids_enabled = {r["webhook_id"] for r in enabled_rows}
    assert ids_enabled == {"wh_b"}


def test_delete_webhook_returns_true_then_false(tmp_path: Path) -> None:
    s = _storage(tmp_path)
    s.insert_webhook(
        webhook_id="wh_del",
        url="https://x.example.com",
        events=["promote.succeeded"],
        secret="s",
        description=None,
        created_at="2026-05-31T00:00:00+00:00",
    )
    assert s.delete_webhook("wh_del") is True
    assert s.delete_webhook("wh_del") is False
    assert s.get_webhook("wh_del") is None
