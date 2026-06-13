"""Async repository for FlowDesk derived snapshots (TimescaleDB).

Thin query layer over asyncpg -- NO heavy ORM. All SQL is held as explicit,
fully double-quoted constants so it is unit-testable without a live database
(see ``tests/test_repo.py``). Covers the replay queries from PRD #10:

  * ``save_snapshot``  -- upsert one snapshot (engine writes one per minute).
  * ``get_snapshot``   -- fetch a single (instrument, session_date, minute).
  * ``list_sessions``  -- available replay dates + minute_count (PRD #10 §2).
  * ``get_range``      -- minute range for replay playback (PRD #10 §2).

asyncpg is imported lazily (only in :func:`create_pool`) so this module -- and
the test suite -- import cleanly in environments where asyncpg is not installed.
The ``payload`` JSONB column is encoded/decoded explicitly with the stdlib
``json`` module (no asyncpg codec) to keep the layer transparent and testable.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

__all__ = [
    "TABLE",
    "INSERT_SQL",
    "GET_SNAPSHOT_SQL",
    "LIST_SESSIONS_SQL",
    "GET_RANGE_SQL",
    "SCHEMA_MIGRATIONS_DDL",
    "MIGRATIONS_DIR",
    "SnapshotRepository",
    "SessionInfo",
    "create_pool",
    "apply_migrations",
    "read_migration",
]

TABLE = '"snapshots"'

# --------------------------------------------------------------------------- #
# SQL (every table/column identifier is double-quoted; params are $1..$N).     #
# --------------------------------------------------------------------------- #
INSERT_SQL = (
    'INSERT INTO "snapshots" '
    '("instrument", "session_date", "ts", "minute_index", "state", '
    '"regime_sign", "forward", "payload") '
    'VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb) '
    'ON CONFLICT ("instrument", "ts") DO UPDATE SET '
    '"session_date" = EXCLUDED."session_date", '
    '"minute_index" = EXCLUDED."minute_index", '
    '"state" = EXCLUDED."state", '
    '"regime_sign" = EXCLUDED."regime_sign", '
    '"forward" = EXCLUDED."forward", '
    '"payload" = EXCLUDED."payload"'
)

GET_SNAPSHOT_SQL = (
    'SELECT "payload" FROM "snapshots" '
    'WHERE "instrument" = $1 AND "session_date" = $2 AND "minute_index" = $3 '
    'LIMIT 1'
)

LIST_SESSIONS_SQL = (
    'SELECT "session_date", COUNT(*) AS "minute_count" FROM "snapshots" '
    'WHERE "instrument" = $1 '
    'GROUP BY "session_date" '
    'ORDER BY "session_date" DESC'
)

GET_RANGE_SQL = (
    'SELECT "payload" FROM "snapshots" '
    'WHERE "instrument" = $1 AND "session_date" = $2 '
    'AND "minute_index" BETWEEN $3 AND $4 '
    'ORDER BY "minute_index" ASC '
    'LIMIT 500'
)

# Migration bookkeeping: a tiny tracking table so each .sql file applies once.
SCHEMA_MIGRATIONS_DDL = (
    'CREATE TABLE IF NOT EXISTS "schema_migrations" ('
    '"filename" TEXT NOT NULL PRIMARY KEY, '
    '"applied_at" TIMESTAMPTZ NOT NULL DEFAULT now())'
)

IS_MIGRATION_APPLIED_SQL = (
    'SELECT 1 FROM "schema_migrations" WHERE "filename" = $1 LIMIT 1'
)

RECORD_MIGRATION_SQL = (
    'INSERT INTO "schema_migrations" ("filename") VALUES ($1) '
    'ON CONFLICT ("filename") DO NOTHING'
)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


# --------------------------------------------------------------------------- #
# Connection/pool protocols (structural -- satisfied by asyncpg + test doubles) #
# --------------------------------------------------------------------------- #
@runtime_checkable
class Connection(Protocol):
    async def execute(self, sql: str, *args: Any) -> Any: ...
    async def fetch(self, sql: str, *args: Any) -> Sequence[Any]: ...
    async def fetchrow(self, sql: str, *args: Any) -> Optional[Any]: ...


class _AcquireContext(Protocol):
    async def __aenter__(self) -> Connection: ...
    async def __aexit__(self, *exc: Any) -> Any: ...


class Pool(Protocol):
    def acquire(self) -> _AcquireContext: ...


class SessionInfo(dict):
    """A replay session entry: ``{"session_date": "YYYY-MM-DD", "minute_count": int}``."""

    def __init__(self, session_date: str, minute_count: int) -> None:
        super().__init__(session_date=session_date, minute_count=minute_count)


# --------------------------------------------------------------------------- #
# Value extraction helpers (Snapshot dict/obj -> column bind values).          #
# --------------------------------------------------------------------------- #
def _as_dict(snapshot: Any) -> Mapping[str, Any]:
    """Normalise a snapshot (pydantic model, JSON string, or mapping) to a dict."""
    if isinstance(snapshot, (str, bytes, bytearray)):
        return json.loads(snapshot)
    model_dump = getattr(snapshot, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    if isinstance(snapshot, Mapping):
        return snapshot
    raise TypeError(f"unsupported snapshot type: {type(snapshot)!r}")


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp (…Z) into an aware UTC datetime."""
    s = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _decode_payload(payload: Any) -> dict[str, Any]:
    """Decode a JSONB payload (asyncpg returns str by default here)."""
    if isinstance(payload, (str, bytes, bytearray)):
        return json.loads(payload)
    if isinstance(payload, Mapping):
        return dict(payload)
    raise TypeError(f"unexpected payload type from DB: {type(payload)!r}")


# --------------------------------------------------------------------------- #
# Repository.                                                                  #
# --------------------------------------------------------------------------- #
class SnapshotRepository:
    """Async data-access for the ``snapshots`` hypertable."""

    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def save_snapshot(self, snapshot: Any) -> None:
        """Upsert one snapshot. Idempotent on the (instrument, ts) primary key."""
        d = _as_dict(snapshot)
        args = (
            str(d["instrument"]),
            date.fromisoformat(str(d["session_date"])),
            _parse_ts(str(d["ts"])),
            int(d["minute_index"]),
            str(d["state"]),
            int(d["regime"]["sign"]),
            float(d["forward"]),
            json.dumps(d, separators=(",", ":")),
        )
        async with self._pool.acquire() as conn:
            await conn.execute(INSERT_SQL, *args)

    async def get_snapshot(
        self, instrument: str, session_date: str, minute_index: int
    ) -> Optional[dict[str, Any]]:
        """Return the snapshot payload for one minute, or None if absent."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                GET_SNAPSHOT_SQL,
                str(instrument),
                date.fromisoformat(str(session_date)),
                int(minute_index),
            )
        if row is None:
            return None
        return _decode_payload(row["payload"])

    async def list_sessions(self, instrument: str) -> list[SessionInfo]:
        """Available replay dates for an instrument (PRD #10 §2), newest first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(LIST_SESSIONS_SQL, str(instrument))
        result: list[SessionInfo] = []
        for row in rows:
            sd = row["session_date"]
            sd_str = sd.isoformat() if isinstance(sd, date) else str(sd)
            result.append(SessionInfo(sd_str, int(row["minute_count"])))
        return result

    async def get_range(
        self,
        instrument: str,
        session_date: str,
        from_minute: int,
        to_minute: int,
    ) -> list[dict[str, Any]]:
        """Ordered snapshot payloads for a minute range (PRD #10 replay playback)."""
        lo, hi = int(from_minute), int(to_minute)
        if lo > hi:  # defensive: swap an inverted range rather than scan nothing
            lo, hi = hi, lo
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                GET_RANGE_SQL,
                str(instrument),
                date.fromisoformat(str(session_date)),
                lo,
                hi,
            )
        return [_decode_payload(row["payload"]) for row in rows]


# --------------------------------------------------------------------------- #
# Pool factory + migration runner (asyncpg imported lazily).                   #
# --------------------------------------------------------------------------- #
async def create_pool(dsn: str, *, min_size: int = 1, max_size: int = 10) -> Pool:
    """Create an asyncpg pool for the given DSN (TIMESCALE_DSN).

    asyncpg is imported here so the module imports without the dependency.
    """
    import asyncpg  # local import: optional at module load time

    return await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)


def read_migration(name: str = "0001_init.sql") -> str:
    """Read a migration SQL file from the migrations directory."""
    return (MIGRATIONS_DIR / name).read_text(encoding="utf-8")


async def apply_migrations(conn: Connection) -> list[str]:
    """Apply every ``.sql`` migration once, in filename order. Idempotent.

    Ensures a ``schema_migrations`` tracking table exists, then for each file in
    ``migrations/`` (sorted by name) skips any already recorded and otherwise
    executes it and records ``filename``/``applied_at``. Safe to call on every
    boot. Returns the filenames applied during this call. asyncpg executes
    multi-statement SQL when invoked with no args.
    """
    await conn.execute(SCHEMA_MIGRATIONS_DDL)
    applied: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name):
        if await conn.fetchrow(IS_MIGRATION_APPLIED_SQL, path.name) is not None:
            continue
        await conn.execute(path.read_text(encoding="utf-8"))
        await conn.execute(RECORD_MIGRATION_SQL, path.name)
        applied.append(path.name)
    return applied
