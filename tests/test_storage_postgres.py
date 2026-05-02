"""Optional PostgreSQL integration (set ``FLIGHTDECK_TEST_POSTGRES_URL``)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from flightdeck.models import ReleaseRecord, WorkspaceConfig
from flightdeck.storage import Storage, storage_from_config

try:
    import psycopg  # noqa: F401
except ImportError:
    psycopg = None

pg_url = os.environ.get("FLIGHTDECK_TEST_POSTGRES_URL", "").strip()
pytestmark = pytest.mark.skipif(
    psycopg is None
    or not pg_url.startswith(("postgresql://", "postgres://")),
    reason="needs psycopg (uv sync --extra postgres) and FLIGHTDECK_TEST_POSTGRES_URL",
)


def test_storage_from_config_uses_database_url() -> None:
    cfg = WorkspaceConfig(db_path=".flightdeck/ignored.db", database_url=pg_url)
    s = storage_from_config(cfg)
    assert s.dialect == "postgresql"
    s.migrate()


def test_postgres_release_roundtrip() -> None:
    s = Storage(dsn=pg_url)
    s.migrate()
    rid = f"rel_pg_{uuid4().hex[:12]}"
    with pytest.raises(ValueError):
        s.get_release(rid)
    rec = ReleaseRecord(
        release_id=rid,
        agent_id="agent_a",
        version="1.0.0",
        environment="local",
        checksum="sha256:aa",
        artifact_json={"api_version": "v1", "kind": "ReleaseArtifact"},
        created_at=datetime.now(tz=timezone.utc),
    )
    s.insert_release(rec)
    got = s.get_release(rid)
    assert got is not None
    assert got.release_id == rid
