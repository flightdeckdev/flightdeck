"""SQLite and PostgreSQL connection helpers for :class:`flightdeck.storage.Storage`."""

from __future__ import annotations

import os
import random
import sqlite3
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Literal

Backend = Literal["sqlite", "postgresql"]


def sqlite_busy_timeout_ms() -> int:
    raw = os.environ.get("FLIGHTDECK_SQLITE_BUSY_TIMEOUT_MS", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return 30_000


def sqlite_lock_retry_enabled() -> bool:
    v = os.environ.get("FLIGHTDECK_SQLITE_RETRY_ON_LOCK", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def sqlite_lock_deadline_seconds() -> float | None:
    """``None`` = do not spin on locked/busy (fail after first error). ``>0`` = wall-clock budget."""
    raw = os.environ.get("FLIGHTDECK_SQLITE_LOCK_TIMEOUT_S", "30").strip()
    try:
        t = float(raw)
    except ValueError:
        t = 30.0
    if t <= 0:
        return None
    return t


def _is_sqlite_busy_or_locked(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


def detect_backend(dsn: str) -> Backend:
    s = dsn.strip()
    if s.startswith(("postgresql://", "postgres://")):
        return "postgresql"
    return "sqlite"


def adapt_placeholders(sql: str, backend: Backend) -> str:
    """SQLite uses ``?``; PostgreSQL (psycopg) uses ``%s`` for parameters."""
    if backend == "sqlite":
        return sql
    return sql.replace("?", "%s")


def json_request_field_predicate(column: str, field: str, backend: Backend) -> str:
    """Equality predicate on ``event_json`` for ``request.<field>`` (parameterized separately)."""
    if backend == "sqlite":
        return f"json_extract({column}, '$.request.{field}') = ?"
    # ``field`` is fixed by callers (trace_id | session_id | span_id); not user-controlled SQL.
    return f"({column}::json->'request'->>'{field}') = ?"


def table_column_names_sqlite(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r["name"]) for r in rows}


def table_column_names_postgres(cur: Any, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name AS name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    rows = cur.fetchall()
    return {str(r["name"]) for r in rows}


def is_unique_violation(backend: Backend, exc: BaseException) -> bool:
    if backend == "sqlite":
        return isinstance(exc, sqlite3.IntegrityError)
    try:
        from psycopg.errors import UniqueViolation
    except ImportError:
        return False
    return isinstance(exc, UniqueViolation)


def require_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as e:
        msg = (
            "PostgreSQL requires the psycopg package. "
            "Install with: uv sync --extra postgres (or pip install 'flightdeck-ai[postgres]')."
        )
        raise ImportError(msg) from e
    return psycopg


class DbCursor:
    """Row cursor for the last ``execute`` (sqlite3 / psycopg)."""

    __slots__ = ("_backend", "_sqlite_cur", "_pg_cur")

    def __init__(self, backend: Backend, sqlite_cur: sqlite3.Cursor | None, pg_cur: Any | None) -> None:
        self._backend = backend
        self._sqlite_cur = sqlite_cur
        self._pg_cur = pg_cur

    def fetchone(self) -> Mapping[str, Any] | None:
        if self._backend == "sqlite":
            assert self._sqlite_cur is not None
            return self._sqlite_cur.fetchone()
        assert self._pg_cur is not None
        return self._pg_cur.fetchone()

    def fetchall(self) -> list[Mapping[str, Any]]:
        if self._backend == "sqlite":
            assert self._sqlite_cur is not None
            return self._sqlite_cur.fetchall()
        assert self._pg_cur is not None
        return self._pg_cur.fetchall()


class DbConn:
    """Unified execute/fetch surface over sqlite3 or psycopg."""

    __slots__ = ("_backend", "_sqlite", "_pg", "_last", "_pg_cur")

    def __init__(self, backend: Backend, sqlite_conn: sqlite3.Connection | None, pg_conn: Any | None) -> None:
        self._backend = backend
        self._sqlite = sqlite_conn
        self._pg = pg_conn
        self._last = DbCursor(backend, None, None)
        self._pg_cur: Any | None = None

    @property
    def backend(self) -> Backend:
        return self._backend

    @property
    def raw_sqlite(self) -> sqlite3.Connection | None:
        return self._sqlite

    @property
    def raw_pg(self) -> Any | None:
        return self._pg

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> DbCursor:
        sql2 = adapt_placeholders(sql, self._backend)
        p = tuple(params) if params is not None else ()
        if self._backend == "sqlite":
            assert self._sqlite is not None
            deadline_s = sqlite_lock_deadline_seconds()
            retry_on = sqlite_lock_retry_enabled() and deadline_s is not None
            start = time.monotonic()
            attempt = 0
            while True:
                try:
                    cur = self._sqlite.execute(sql2, p)
                    self._last = DbCursor(self._backend, cur, None)
                    return self._last
                except sqlite3.OperationalError as e:
                    if not retry_on or not _is_sqlite_busy_or_locked(e):
                        raise
                    elapsed = time.monotonic() - start
                    if elapsed >= deadline_s:
                        raise
                    cap = deadline_s - elapsed
                    sleep = min(0.05 * (2 ** min(attempt, 8)), 1.0) * (0.5 + random.random())
                    time.sleep(min(sleep, cap))
                    attempt += 1
        assert self._pg is not None
        require_psycopg()
        from psycopg.rows import dict_row

        if self._pg_cur is not None:
            self._pg_cur.close()
            self._pg_cur = None
        self._pg_cur = self._pg.cursor(row_factory=dict_row)
        self._pg_cur.execute(sql2, p)
        self._last = DbCursor(self._backend, None, self._pg_cur)
        return self._last

    def close_last_pg_cursor(self) -> None:
        if self._backend == "postgresql" and self._pg_cur is not None:
            self._pg_cur.close()
            self._pg_cur = None

    def table_columns(self, table: str) -> set[str]:
        if self._backend == "sqlite":
            assert self._sqlite is not None
            return table_column_names_sqlite(self._sqlite, table)
        assert self._pg is not None
        require_psycopg()
        from psycopg.rows import dict_row

        with self._pg.cursor(row_factory=dict_row) as cur:
            return table_column_names_postgres(cur, table)

    def fetchone(self) -> Mapping[str, Any] | None:
        return self._last.fetchone()

    def fetchall(self) -> list[Mapping[str, Any]]:
        return self._last.fetchall()


def configure_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    busy = sqlite_busy_timeout_ms()
    # PRAGMA busy_timeout does not accept bound parameters on all SQLite builds.
    conn.execute(f"PRAGMA busy_timeout={int(busy)};")


@contextmanager
def open_sqlite(dsn: str) -> Iterator[DbConn]:
    with sqlite3.connect(dsn) as conn:
        conn.row_factory = sqlite3.Row
        configure_sqlite(conn)
        yield DbConn("sqlite", conn, None)


@contextmanager
def open_postgres(dsn: str) -> Iterator[DbConn]:
    psycopg = require_psycopg()
    conn = psycopg.connect(dsn, autocommit=False)
    wrapper: DbConn | None = None
    try:
        wrapper = DbConn("postgresql", None, conn)
        yield wrapper
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if wrapper is not None:
            wrapper.close_last_pg_cursor()
        conn.close()


@contextmanager
def open_postgres_transaction(dsn: str) -> Iterator[DbConn]:
    psycopg = require_psycopg()
    conn = psycopg.connect(dsn, autocommit=False)
    wrapper: DbConn | None = None
    try:
        wrapper = DbConn("postgresql", None, conn)
        with conn.transaction():
            yield wrapper
    finally:
        if wrapper is not None:
            wrapper.close_last_pg_cursor()
        conn.close()
