"""Tests for the Redis current-state layer using fakeredis (no live server).

Verifies:
  * key/channel names match the documented scheme;
  * set_now -> get_now round-trips the full snapshot payload;
  * set_now publishes a message a subscriber actually receives (pub/sub fan-out);
  * set_session/get_session round-trip.

These drive the async API via ``asyncio.run`` so they pass under pytest with no
asyncio plugin, and read cleanly "by inspection" (per the task's acceptance) in
environments where redis/fakeredis are not installed.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import fakeredis.aioredis

from api.state import (
    NOW_KEY,
    SESSION_KEY,
    UPDATES_CHANNEL,
    StateStore,
    now_key,
    session_key,
    updates_channel,
)

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


def _fake() -> Any:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def test_key_scheme_matches_documented_names() -> None:
    assert NOW_KEY == "flowdesk:now:{instrument}"
    assert SESSION_KEY == "flowdesk:session:{instrument}"
    assert UPDATES_CHANNEL == "flowdesk:updates:{instrument}"
    assert now_key("ES") == "flowdesk:now:ES"
    assert session_key("NQ") == "flowdesk:session:NQ"
    assert updates_channel("ES") == "flowdesk:updates:ES"


def test_set_now_get_now_round_trip() -> None:
    async def run() -> None:
        store = StateStore(_fake())
        await store.set_now("ES", SAMPLE)
        got = await store.get_now("ES")
        assert got == SAMPLE
        # Stored under the documented key, as JSON.
        raw = await store.client.get(now_key("ES"))
        assert json.loads(raw) == SAMPLE
        # Unset instrument -> None.
        assert await store.get_now("NQ") is None

    asyncio.run(run())


def test_set_now_publishes_to_subscriber() -> None:
    async def run() -> None:
        store = StateStore(_fake())
        async with store.subscribe("ES") as sub:
            gen = sub.messages()
            # Publish AFTER subscribing so the subscriber receives it.
            await store.set_now("ES", SAMPLE)
            msg = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
        assert msg == SAMPLE

    asyncio.run(run())


def test_subscriber_only_receives_its_instrument_channel() -> None:
    async def run() -> None:
        store = StateStore(_fake())
        async with store.subscribe("ES") as sub:
            gen = sub.messages()
            # Publish on a DIFFERENT instrument first; must not be received.
            await store.set_now("NQ", {**SAMPLE, "instrument": "NQ"})
            await store.set_now("ES", SAMPLE)
            msg = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
        assert msg["instrument"] == "ES"

    asyncio.run(run())


def test_set_session_get_session_round_trip() -> None:
    async def run() -> None:
        store = StateStore(_fake())
        assert await store.get_session("ES") is None
        await store.set_session("ES", "LIVE")
        assert await store.get_session("ES") == "LIVE"
        # Stored under the documented key.
        assert await store.client.get(session_key("ES")) == "LIVE"

    asyncio.run(run())


def test_set_now_accepts_json_string_input() -> None:
    async def run() -> None:
        store = StateStore(_fake())
        await store.set_now("ES", json.dumps(SAMPLE))
        assert await store.get_now("ES") == SAMPLE

    asyncio.run(run())
