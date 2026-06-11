"""Unit tests for the snapshot repository -- NO live database required.

Uses a recording test-double (``FakePool`` / ``FakeConnection``) that captures
every (sql, args) pair and returns canned rows. Tests assert:
  * SQL strings target the correct table/columns, fully double-quoted;
  * positional parameters ($1..$N) are sequential and bound in the right order;
  * bind-value SHAPES are correct (str / date / aware-datetime / int / json-str);
  * replay queries (PRD #10) return correctly decoded payloads.

Run (real integration test against Timescale) -- see db/README.md.

These tests are plain functions that drive the async repo via ``asyncio.run``,
so they execute under pytest OR the bundled inline harness (no pytest-asyncio).
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from db.repo import (
    GET_RANGE_SQL,
    GET_SNAPSHOT_SQL,
    INSERT_SQL,
    LIST_SESSIONS_SQL,
    SnapshotRepository,
)

# --------------------------------------------------------------------------- #
# Sample snapshot (canonical shape, PRD #8 §3).                                #
# --------------------------------------------------------------------------- #
SAMPLE: dict[str, Any] = {
    "schema_version": 1,
    "instrument": "ES",
    "session_date": "2026-06-10",
    "ts": "2026-06-10T13:31:00Z",
    "minute_index": 1,
    "state": "LIVE",
    "stale": False,
    "expired": False,
    "forward": 5000.25,
    "rate": 0.0531,
    "axis": {"strike_min": 4950, "strike_max": 5050, "step": 5},
    "regime": {"net_gamma": -9718772.87, "sign": -1, "stability_pct": 4.1708},
    "profile": [{"strike": 5000, "net_gex": 1.0, "net_dex": 2.0, "interpolated": False}],
    "field": {"price_grid": [5000.0], "gamma": [1.0], "delta": [2.0]},
    "levels": {
        "call_walls": [5010],
        "put_walls": [4990],
        "gamma_flip": None,
        "largest_gex": 4980,
        "largest_dex": 5010,
    },
}


# --------------------------------------------------------------------------- #
# Recording test-double.                                                       #
# --------------------------------------------------------------------------- #
class FakeConnection:
    def __init__(
        self,
        *,
        fetch_rows: Optional[Sequence[Any]] = None,
        fetchrow_result: Optional[Any] = None,
    ) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self._fetch_rows = list(fetch_rows or [])
        self._fetchrow_result = fetchrow_result

    async def execute(self, sql: str, *args: Any) -> str:
        self.calls.append(("execute", sql, args))
        return "INSERT 0 1"

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        self.calls.append(("fetch", sql, args))
        return list(self._fetch_rows)

    async def fetchrow(self, sql: str, *args: Any) -> Optional[Any]:
        self.calls.append(("fetchrow", sql, args))
        return self._fetchrow_result


class _Acquire:
    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self._conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class FakePool:
    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


def _placeholders(sql: str) -> list[int]:
    return [int(n) for n in re.findall(r"\$(\d+)", sql)]


def _assert_sequential_placeholders(sql: str) -> None:
    nums = _placeholders(sql)
    assert nums, f"no placeholders found in: {sql}"
    uniq = sorted(set(nums))
    assert uniq == list(range(1, max(nums) + 1)), f"non-sequential placeholders: {nums}"


def _assert_table_quoted(sql: str) -> None:
    # Every occurrence of the table name must be double-quoted.
    assert '"snapshots"' in sql
    assert re.search(r'(?<!")snapshots(?!")', sql) is None, f"bare table name in: {sql}"


# --------------------------------------------------------------------------- #
# Tests.                                                                       #
# --------------------------------------------------------------------------- #
def test_save_snapshot_sql_and_param_shapes() -> None:
    conn = FakeConnection()
    repo = SnapshotRepository(FakePool(conn))
    asyncio.run(repo.save_snapshot(SAMPLE))

    assert len(conn.calls) == 1
    method, sql, args = conn.calls[0]
    assert method == "execute"

    _assert_table_quoted(sql)
    _assert_sequential_placeholders(sql)
    assert sql.startswith('INSERT INTO "snapshots"')
    assert 'ON CONFLICT ("instrument", "ts")' in sql
    assert "$8::jsonb" in sql
    for col in (
        "instrument",
        "session_date",
        "ts",
        "minute_index",
        "state",
        "regime_sign",
        "forward",
        "payload",
    ):
        assert f'"{col}"' in sql, f"column not quoted: {col}"

    # 8 params, in the documented order.
    assert len(args) == 8
    assert args[0] == "ES" and isinstance(args[0], str)
    assert args[1] == date(2026, 6, 10) and isinstance(args[1], date)
    assert isinstance(args[2], datetime) and args[2].utcoffset() == timedelta(0)
    assert args[2] == datetime(2026, 6, 10, 13, 31, tzinfo=timezone.utc)
    assert args[3] == 1 and isinstance(args[3], int)
    assert args[4] == "LIVE"
    assert args[5] == -1 and isinstance(args[5], int)
    assert args[6] == 5000.25 and isinstance(args[6], float)
    assert isinstance(args[7], str)
    assert json.loads(args[7]) == SAMPLE  # full payload round-trips


def test_get_snapshot_query_and_decode() -> None:
    payload_str = json.dumps(SAMPLE)
    conn = FakeConnection(fetchrow_result={"payload": payload_str})
    repo = SnapshotRepository(FakePool(conn))
    out = asyncio.run(repo.get_snapshot("ES", "2026-06-10", 1))

    method, sql, args = conn.calls[0]
    assert method == "fetchrow"
    assert sql == GET_SNAPSHOT_SQL
    _assert_table_quoted(sql)
    _assert_sequential_placeholders(sql)
    assert "LIMIT 1" in sql
    assert '"minute_index" = $3' in sql
    assert args == ("ES", date(2026, 6, 10), 1)
    assert isinstance(args[1], date) and isinstance(args[2], int)
    assert out == SAMPLE


def test_get_snapshot_returns_none_when_absent() -> None:
    conn = FakeConnection(fetchrow_result=None)
    repo = SnapshotRepository(FakePool(conn))
    out = asyncio.run(repo.get_snapshot("NQ", "2026-06-10", 999))
    assert out is None


def test_list_sessions_query_and_shape() -> None:
    rows = [
        {"session_date": date(2026, 6, 10), "minute_count": 390},
        {"session_date": date(2026, 6, 9), "minute_count": 388},
    ]
    conn = FakeConnection(fetch_rows=rows)
    repo = SnapshotRepository(FakePool(conn))
    out = asyncio.run(repo.list_sessions("ES"))

    method, sql, args = conn.calls[0]
    assert method == "fetch"
    assert sql == LIST_SESSIONS_SQL
    _assert_table_quoted(sql)
    _assert_sequential_placeholders(sql)
    assert 'COUNT(*) AS "minute_count"' in sql
    assert 'GROUP BY "session_date"' in sql
    assert 'ORDER BY "session_date" DESC' in sql
    assert args == ("ES",)
    assert out == [
        {"session_date": "2026-06-10", "minute_count": 390},
        {"session_date": "2026-06-09", "minute_count": 388},
    ]


def test_get_range_query_and_decode() -> None:
    rows = [
        {"payload": json.dumps(SAMPLE)},
        {"payload": json.dumps({**SAMPLE, "minute_index": 2, "ts": "2026-06-10T13:32:00Z"})},
    ]
    conn = FakeConnection(fetch_rows=rows)
    repo = SnapshotRepository(FakePool(conn))
    out = asyncio.run(repo.get_range("ES", "2026-06-10", 0, 389))

    method, sql, args = conn.calls[0]
    assert method == "fetch"
    assert sql == GET_RANGE_SQL
    _assert_table_quoted(sql)
    _assert_sequential_placeholders(sql)
    assert '"minute_index" BETWEEN $3 AND $4' in sql
    assert 'ORDER BY "minute_index" ASC' in sql
    assert args == ("ES", date(2026, 6, 10), 0, 389)
    assert isinstance(args[2], int) and isinstance(args[3], int)
    assert len(out) == 2
    assert out[0]["minute_index"] == 1 and out[1]["minute_index"] == 2


def test_all_sql_constants_quote_table_and_sequential_params() -> None:
    for sql in (INSERT_SQL, GET_SNAPSHOT_SQL, LIST_SESSIONS_SQL, GET_RANGE_SQL):
        _assert_table_quoted(sql)
        _assert_sequential_placeholders(sql)


def test_param_counts_match_placeholders() -> None:
    cases = [
        (INSERT_SQL, 8),
        (GET_SNAPSHOT_SQL, 3),
        (LIST_SESSIONS_SQL, 1),
        (GET_RANGE_SQL, 4),
    ]
    for sql, expected in cases:
        assert max(_placeholders(sql)) == expected, f"expected {expected} params in: {sql}"


def test_save_snapshot_accepts_json_string_and_model_like() -> None:
    # JSON string input.
    conn1 = FakeConnection()
    asyncio.run(SnapshotRepository(FakePool(conn1)).save_snapshot(json.dumps(SAMPLE)))
    assert conn1.calls[0][2][0] == "ES"

    # Pydantic-like object exposing model_dump().
    class _ModelLike:
        def model_dump(self) -> dict[str, Any]:
            return dict(SAMPLE)

    conn2 = FakeConnection()
    asyncio.run(SnapshotRepository(FakePool(conn2)).save_snapshot(_ModelLike()))
    assert conn2.calls[0][2][5] == -1  # regime_sign extracted
