from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from flightdeck.models import Policy, PolicyResult, PricingTable, PromotionRecord, ReleaseRecord, RunEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_parent_dir(db_path: str) -> None:
    Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


# Highest migration version applied by `Storage.migrate()` — keep in sync with migration blocks below.
LATEST_SCHEMA_MIGRATION_VERSION = 3


@dataclass(frozen=True)
class Storage:
    db_path: str

    @staticmethod
    def _configure_connection(conn: sqlite3.Connection) -> None:
        # Improve concurrency + reduce "database is locked" surprises on Windows.
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")

    def connect(self) -> sqlite3.Connection:
        ensure_parent_dir(self.db_path)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        self._configure_connection(conn)
        return conn

    @contextmanager
    def transaction(self) -> Any:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version INTEGER PRIMARY KEY
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS releases (
                  release_id TEXT PRIMARY KEY,
                  agent_id TEXT NOT NULL,
                  version TEXT NOT NULL,
                  environment TEXT NOT NULL,
                  checksum TEXT NOT NULL,
                  artifact_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pricing_tables (
                  provider TEXT NOT NULL,
                  pricing_version TEXT NOT NULL,
                  pricing_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY (provider, pricing_version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pricing_import_audit (
                  import_id TEXT PRIMARY KEY,
                  provider TEXT NOT NULL,
                  pricing_version TEXT NOT NULL,
                  action TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  reason TEXT,
                  old_pricing_json TEXT,
                  new_pricing_json TEXT NOT NULL,
                  new_checksum TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                  run_id TEXT PRIMARY KEY,
                  release_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  task_id TEXT NOT NULL,
                  environment TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  event_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS active_policy (
                  policy_id TEXT PRIMARY KEY,
                  policy_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS promoted_releases (
                  agent_id TEXT NOT NULL,
                  environment TEXT NOT NULL,
                  release_id TEXT NOT NULL,
                  promoted_at TEXT NOT NULL,
                  PRIMARY KEY (agent_id, environment)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS release_actions (
                  action_id TEXT PRIMARY KEY,
                  action TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  release_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  environment TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  policy_result_json TEXT NOT NULL,
                  baseline_release_id TEXT,
                  created_at TEXT NOT NULL
                )
                """
            )

            applied = {int(r["version"]) for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}

            def apply(version: int, statements: list[str]) -> None:
                if version in applied:
                    return
                for stmt in statements:
                    conn.execute(stmt)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
                applied.add(version)

            # v1: reserved for the initial schema created via CREATE TABLE IF NOT EXISTS above.
            apply(1, ["SELECT 1;"])

            # v2: query performance for diff / run lookups by release.
            apply(
                2,
                [
                    "CREATE INDEX IF NOT EXISTS idx_run_events_release_timestamp "
                    "ON run_events(release_id, timestamp);",
                ],
            )

            # v3: monotonic audit_seq on release_actions (append-only promotion/rollback ledger).
            if 3 not in applied:
                cols = {r["name"] for r in conn.execute("PRAGMA table_info(release_actions)").fetchall()}
                if "audit_seq" not in cols:
                    conn.execute("ALTER TABLE release_actions ADD COLUMN audit_seq INTEGER")
                pending = conn.execute(
                    """
                    SELECT action_id FROM release_actions
                    WHERE audit_seq IS NULL
                    ORDER BY created_at, action_id
                    """
                ).fetchall()
                if pending:
                    base_row = conn.execute("SELECT COALESCE(MAX(audit_seq), 0) FROM release_actions").fetchone()
                    n = int(base_row[0]) if base_row is not None else 0
                    for pr in pending:
                        n += 1
                        conn.execute(
                            "UPDATE release_actions SET audit_seq = ? WHERE action_id = ?",
                            (n, pr["action_id"]),
                        )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_release_actions_audit_seq "
                    "ON release_actions(audit_seq)"
                )
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (3,))
                applied.add(3)

    def list_applied_migrations(self) -> list[int]:
        """Return applied schema migration versions (requires tables to exist; call `migrate()` first)."""
        with self.connect() as conn:
            rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        return [int(r["version"]) for r in rows]

    def list_promoted_pointers(self) -> list[tuple[str, str, str]]:
        """Each tuple is (agent_id, environment, release_id)."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT agent_id, environment, release_id FROM promoted_releases ORDER BY agent_id, environment"
            ).fetchall()
        return [(str(r["agent_id"]), str(r["environment"]), str(r["release_id"])) for r in rows]

    def check_release_actions_audit_seq(self) -> tuple[bool, str]:
        """
        Verify `audit_seq` is present, non-null, unique, and contiguous from 1..max
        (best-effort tamper / partial-write detection for the append-only ledger).
        """
        self.migrate()
        with self.connect() as conn:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(release_actions)").fetchall()}
            if "audit_seq" not in cols:
                return False, "release_actions has no audit_seq column (migrations incomplete?)"
            rows = conn.execute("SELECT audit_seq FROM release_actions ORDER BY audit_seq").fetchall()
        if not rows:
            return True, "no release_actions rows"
        seqs = [r["audit_seq"] for r in rows]
        if any(s is None for s in seqs):
            return False, "NULL audit_seq in release_actions"
        ints = [int(s) for s in seqs]
        m = max(ints)
        want = set(range(1, m + 1))
        got = set(ints)
        if want != got:
            missing = sorted(want - got)
            extra = sorted(got - want)
            return False, f"expected contiguous 1..{m}; missing={missing} extra={extra} (got={sorted(got)})"
        if len(ints) != len(set(ints)):
            return False, "duplicate audit_seq values"
        return True, f"contiguous 1..{m} ({len(ints)} row(s))"

    def insert_pricing_table(
        self,
        table: PricingTable,
        *,
        replace: bool = False,
        actor: str,
        reason: str | None = None,
    ) -> None:
        new_json = json.dumps(table.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        new_checksum = hashlib.sha256(new_json.encode("utf-8")).hexdigest()

        with self.transaction() as conn:
            row = conn.execute(
                """
                SELECT pricing_json FROM pricing_tables
                WHERE provider = ? AND pricing_version = ?
                """,
                (table.provider, table.pricing_version),
            ).fetchone()

            if row and not replace:
                raise ValueError(
                    f"Pricing table already exists for {table.provider}/{table.pricing_version}. "
                    f"Use --replace to override."
                )

            old_json = str(row["pricing_json"]) if row else None

            if row and replace:
                if not reason:
                    raise ValueError("--reason is required when using --replace for pricing imports.")

                conn.execute(
                    """
                    UPDATE pricing_tables
                    SET pricing_json = ?, created_at = ?
                    WHERE provider = ? AND pricing_version = ?
                    """,
                    (
                        new_json,
                        utc_now().isoformat(),
                        table.provider,
                        table.pricing_version,
                    ),
                )
                action = "replace"
            else:
                conn.execute(
                    """
                    INSERT INTO pricing_tables (provider, pricing_version, pricing_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        table.provider,
                        table.pricing_version,
                        new_json,
                        utc_now().isoformat(),
                    ),
                )
                action = "insert"

            conn.execute(
                """
                INSERT INTO pricing_import_audit
                  (import_id, provider, pricing_version, action, actor, reason, old_pricing_json, new_pricing_json, new_checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"pim_{uuid4().hex[:12]}",
                    table.provider,
                    table.pricing_version,
                    action,
                    actor,
                    reason,
                    old_json,
                    new_json,
                    new_checksum,
                    utc_now().isoformat(),
                ),
            )

    def insert_release(self, record: ReleaseRecord) -> None:
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT 1 FROM releases WHERE release_id = ?",
                (record.release_id,),
            ).fetchone()
            if existing:
                raise ValueError(f"Release already exists: {record.release_id}")

            conn.execute(
                """
                INSERT INTO releases
                  (release_id, agent_id, version, environment, checksum, artifact_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.release_id,
                    record.agent_id,
                    record.version,
                    record.environment,
                    record.checksum,
                    json.dumps(record.artifact_json, sort_keys=True),
                    record.created_at.isoformat(),
                ),
            )

    def get_release(self, release_id: str) -> ReleaseRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM releases WHERE release_id = ?",
                (release_id,),
            ).fetchone()
            if not row:
                return None
            return ReleaseRecord(
                release_id=row["release_id"],
                agent_id=row["agent_id"],
                version=row["version"],
                environment=row["environment"],
                checksum=row["checksum"],
                artifact_json=json.loads(row["artifact_json"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_releases(self) -> list[ReleaseRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM releases ORDER BY created_at DESC",
            ).fetchall()
            return [
                ReleaseRecord(
                    release_id=r["release_id"],
                    agent_id=r["agent_id"],
                    version=r["version"],
                    environment=r["environment"],
                    checksum=r["checksum"],
                    artifact_json=json.loads(r["artifact_json"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]

    def get_pricing_table(self, provider: str, pricing_version: str) -> PricingTable | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT pricing_json FROM pricing_tables
                WHERE provider = ? AND pricing_version = ?
                """,
                (provider, pricing_version),
            ).fetchone()
            if not row:
                return None
            return PricingTable.model_validate_json(row["pricing_json"])

    def set_active_policy(self, policy: Policy) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO active_policy (policy_id, policy_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(policy_id) DO UPDATE SET
                  policy_json = excluded.policy_json,
                  updated_at = excluded.updated_at
                """,
                (policy.policy_id, policy.model_dump_json(), utc_now().isoformat()),
            )

    def get_active_policy(self) -> Policy | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT policy_json FROM active_policy
                ORDER BY updated_at DESC
                LIMIT 1
                """,
            ).fetchone()
            if not row:
                return None
            return Policy.model_validate_json(row["policy_json"])

    def get_promoted_release_id(self, agent_id: str, environment: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT release_id FROM promoted_releases
                WHERE agent_id = ? AND environment = ?
                """,
                (agent_id, environment),
            ).fetchone()
            if not row:
                return None
            return str(row["release_id"])

    @staticmethod
    def _set_promoted_release_conn(conn: sqlite3.Connection, agent_id: str, environment: str, release_id: str) -> None:
        conn.execute(
            """
            INSERT INTO promoted_releases (agent_id, environment, release_id, promoted_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(agent_id, environment) DO UPDATE SET
              release_id = excluded.release_id,
              promoted_at = excluded.promoted_at
            """,
            (agent_id, environment, release_id, utc_now().isoformat()),
        )

    def set_promoted_release(self, agent_id: str, environment: str, release_id: str) -> None:
        with self.connect() as conn:
            self._set_promoted_release_conn(conn, agent_id, environment, release_id)

    @staticmethod
    def _next_audit_seq(conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COALESCE(MAX(audit_seq), 0) + 1 AS n FROM release_actions").fetchone()
        return int(row["n"])

    @staticmethod
    def _insert_release_action_conn(conn: sqlite3.Connection, record: PromotionRecord) -> None:
        audit_seq = record.audit_seq
        if audit_seq is None:
            audit_seq = Storage._next_audit_seq(conn)
        conn.execute(
            """
            INSERT INTO release_actions
              (
                action_id,
                action,
                actor,
                release_id,
                agent_id,
                environment,
                reason,
                policy_result_json,
                baseline_release_id,
                created_at,
                audit_seq
              )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.action_id,
                record.action,
                record.actor,
                record.release_id,
                record.agent_id,
                record.environment,
                record.reason,
                record.policy_result.model_dump_json(),
                record.baseline_release_id,
                record.created_at.isoformat(),
                audit_seq,
            ),
        )

    def insert_promotion_record(self, record: PromotionRecord) -> None:
        with self.connect() as conn:
            self._insert_release_action_conn(conn, record)

    def commit_promotion(self, record: PromotionRecord, *, new_promoted_release_id: str) -> None:
        """
        Atomically persist the audit record and update the promoted pointer.
        """
        with self.transaction() as conn:
            self._insert_release_action_conn(conn, record)
            self._set_promoted_release_conn(conn, record.agent_id, record.environment, new_promoted_release_id)

    def list_release_actions(
        self,
        agent_id: str | None = None,
        environment: str | None = None,
    ) -> list[PromotionRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if agent_id:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if environment:
            clauses.append("environment = ?")
            params.append(environment)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM release_actions
                {where}
                ORDER BY created_at DESC
                """,
                tuple(params),
            ).fetchall()

            out: list[PromotionRecord] = []
            for r in rows:
                audit_seq_v: int | None = None
                if "audit_seq" in r.keys() and r["audit_seq"] is not None:
                    audit_seq_v = int(r["audit_seq"])
                out.append(
                    PromotionRecord(
                        action_id=r["action_id"],
                        action=r["action"],
                        actor=r["actor"],
                        release_id=r["release_id"],
                        agent_id=r["agent_id"],
                        environment=r["environment"],
                        reason=r["reason"],
                        policy_result=PolicyResult.model_validate_json(r["policy_result_json"]),
                        baseline_release_id=r["baseline_release_id"],
                        created_at=datetime.fromisoformat(r["created_at"]),
                        audit_seq=audit_seq_v,
                    )
                )
            return out

    def insert_run_events(self, events: Iterable[RunEvent]) -> int:
        rows = []
        for e in events:
            rows.append(
                (
                    e.run_id,
                    e.release_id,
                    e.agent_id,
                    e.tenant_id,
                    e.task_id,
                    e.environment,
                    e.timestamp.isoformat(),
                    e.model_dump_json(),
                )
            )

        with self.connect() as conn:
            inserted = 0
            for row in rows:
                try:
                    conn.execute(
                        """
                        INSERT INTO run_events
                          (run_id, release_id, agent_id, tenant_id, task_id, environment, timestamp, event_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        row,
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    # idempotent ingestion
                    pass
            return inserted

    def query_runs(
        self,
        release_id: str,
        since: datetime,
        until: datetime,
        tenant_id: str | None = None,
        task_id: str | None = None,
        environment: str | None = None,
    ) -> list[RunEvent]:
        clauses: list[str] = ["release_id = ?", "timestamp >= ?", "timestamp < ?"]
        params: list[Any] = [release_id, since.isoformat(), until.isoformat()]

        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(tenant_id)
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if environment:
            clauses.append("environment = ?")
            params.append(environment)

        where = " AND ".join(clauses)

        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT event_json FROM run_events WHERE {where}",
                tuple(params),
            ).fetchall()
            return [RunEvent.model_validate_json(r["event_json"]) for r in rows]

