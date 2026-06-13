"""WebSocket tests — FastAPI/Starlette TestClient with a mocked Redis pub/sub.

Covers:
  * connect-snapshot (current state delivered right after connect);
  * push on publish (engine update fanned out from the pub/sub channel);
  * STALE passthrough (state="STALE"/stale=true frame forwarded unchanged);
  * heartbeat ping (+ client pong accepted);
  * gating close codes 4401 (no session) and 4403 (no DESK);
  * bad instrument close code 4400.

The pub/sub is faked: the store exposes ``subscribe(instrument)`` returning an
async context manager whose ``messages()`` async-iterator drains an
``asyncio.Queue`` pre-seeded by the test. Because TestClient drives the app on
its own event loop, we seed the channel BEFORE connecting so the fan-out task
delivers deterministically.

Run: pip install -e ".[dev]" && pytest tests/test_ws.py -q
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Optional

import pytest
from starlette.websockets import WebSocketDisconnect

from api.auth_session import Session, serialize_session
from api.main import create_app
from api.security import SESSION_COOKIE

# Signing secret for the test session cookies (release-1.5+ signed-cookie scheme;
# the app verifies with os.environ["SESSION_SECRET"]). See tests/AUTH_TEST_NOTES.md.
SECRET = "test-secret-please-change"  # test-only, not from prod

# Valid Snapshot per engine/schema.py (axis.step; regime.sign int; level lists).
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
    "axis": {"strike_min": 4950.0, "strike_max": 5050.0, "step": 5.0},
    "regime": {"net_gamma": -9718772.87, "sign": -1, "stability_pct": 4.1708},
    "profile": [{"strike": 5000.0, "net_gex": 1.0, "net_dex": 2.0, "interpolated": False}],
    "field": {"price_grid": [5000.0], "gamma": [1.0], "delta": [2.0]},
    "levels": {
        "call_walls": [5010.0],
        "put_walls": [4990.0],
        "gamma_flip": None,
        "largest_gex": 4980.0,
        "largest_dex": 5010.0,
    },
}


def _next_minute(stale: bool = False) -> dict[str, Any]:
    nxt = json.loads(json.dumps(SAMPLE))
    nxt["minute_index"] = 2
    nxt["ts"] = "2026-06-10T13:32:00Z"
    if stale:
        nxt["state"] = "STALE"
        nxt["stale"] = True
    return nxt


def _desk_cookie() -> str:
    return serialize_session(
        Session(discord_id="123", has_desk=True, is_member=True), SECRET
    )


def _no_desk_cookie() -> str:
    return serialize_session(
        Session(discord_id="123", has_desk=False, is_member=True), SECRET
    )


class _FakeSubscription:
    def __init__(self, queue: "asyncio.Queue[Optional[dict[str, Any]]]") -> None:
        self._queue = queue

    async def __aenter__(self) -> "_FakeSubscription":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def messages(self):
        while True:
            item = await self._queue.get()
            if item is None:  # sentinel
                return
            yield item


class FakeStore:
    """Mimics api.state.StateStore for the WS layer (get_now + subscribe)."""

    def __init__(self, now: Optional[dict[str, Any]] = None) -> None:
        self._now = now
        self.channel: "asyncio.Queue[Optional[dict[str, Any]]]" = asyncio.Queue()

    async def get_now(self, instrument: str) -> Optional[dict[str, Any]]:
        return self._now

    def subscribe(self, instrument: str) -> _FakeSubscription:
        return _FakeSubscription(self.channel)

    def seed(self, snapshot: dict[str, Any]) -> None:
        self.channel.put_nowait(snapshot)


def make_app(store: FakeStore):
    os.environ["SESSION_SECRET"] = SECRET
    os.environ["DISCORD_GUILD_ID"] = "guild-1"
    os.environ["DISCORD_DESK_ROLE_ID"] = "role-desk"
    app = create_app()
    app.state.state_store = store
    return app


def _client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


# --------------------------------------------------------------------------- #
# Gating close codes.                                                          #
# --------------------------------------------------------------------------- #
def test_ws_4401_without_session() -> None:
    client = _client(make_app(FakeStore(now=SAMPLE)))
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws?instrument=ES"):
            pass
    assert exc.value.code == 4401


def test_ws_4403_for_non_desk() -> None:  # T-09
    client = _client(make_app(FakeStore(now=SAMPLE)))
    client.cookies.set(SESSION_COOKIE, _no_desk_cookie())
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws?instrument=ES"):
            pass
    assert exc.value.code == 4403


def test_ws_4400_bad_instrument() -> None:
    client = _client(make_app(FakeStore(now=SAMPLE)))
    client.cookies.set(SESSION_COOKIE, _desk_cookie())
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws?instrument=XX"):
            pass
    assert exc.value.code == 4400


# --------------------------------------------------------------------------- #
# Connect-snapshot + push on publish + STALE passthrough.                      #
# --------------------------------------------------------------------------- #
def test_ws_connect_snapshot_and_push() -> None:
    store = FakeStore(now=SAMPLE)
    store.seed(_next_minute())  # delivered as a pub/sub push after connect
    client = _client(make_app(store))
    client.cookies.set(SESSION_COOKIE, _desk_cookie())
    with client.websocket_connect("/ws?instrument=ES") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert first["data"]["minute_index"] == 1  # current state on connect

        second = ws.receive_json()
        assert second["type"] == "snapshot"
        assert second["data"]["minute_index"] == 2  # pushed engine update


def test_ws_stale_passthrough() -> None:
    store = FakeStore(now=SAMPLE)
    store.seed(_next_minute(stale=True))
    client = _client(make_app(store))
    client.cookies.set(SESSION_COOKIE, _desk_cookie())
    with client.websocket_connect("/ws?instrument=ES") as ws:
        ws.receive_json()  # connect snapshot (LIVE)
        stale = ws.receive_json()
        assert stale["type"] == "snapshot"
        assert stale["data"]["state"] == "STALE"
        assert stale["data"]["stale"] is True


# --------------------------------------------------------------------------- #
# Heartbeat ping + client pong.                                                #
# --------------------------------------------------------------------------- #
def test_ws_heartbeat_ping_and_pong(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WS_HEARTBEAT_S", "0.05")
    store = FakeStore(now=None)  # no connect snapshot; first frame is the ping
    client = _client(make_app(store))
    client.cookies.set(SESSION_COOKIE, _desk_cookie())
    with client.websocket_connect("/ws?instrument=ES") as ws:
        frame = ws.receive_json()
        assert frame == {"type": "ping"}
        ws.send_json({"type": "pong"})  # accepted/ignored by the receive loop
        frame2 = ws.receive_json()
        assert frame2 == {"type": "ping"}  # heartbeat keeps going
