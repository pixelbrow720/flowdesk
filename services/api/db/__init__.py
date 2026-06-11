"""FlowDesk API persistence layer (TimescaleDB, thin asyncpg query layer)."""
from __future__ import annotations

from .repo import (
    GET_RANGE_SQL,
    GET_SNAPSHOT_SQL,
    INSERT_SQL,
    LIST_SESSIONS_SQL,
    MIGRATIONS_DIR,
    TABLE,
    SessionInfo,
    SnapshotRepository,
    apply_migrations,
    create_pool,
    read_migration,
)

__all__ = [
    "GET_RANGE_SQL",
    "GET_SNAPSHOT_SQL",
    "INSERT_SQL",
    "LIST_SESSIONS_SQL",
    "MIGRATIONS_DIR",
    "TABLE",
    "SessionInfo",
    "SnapshotRepository",
    "apply_migrations",
    "create_pool",
    "read_migration",
]
