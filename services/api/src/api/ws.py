"""FlowDesk WebSocket endpoint + pub/sub connection manager (PRD #8 §7).

Endpoint
--------
``GET /ws?instrument=ES|NQ`` (WebSocket upgrade). Streams the latest snapshot on
connect and on every new minute (engine update) via Redis pub/sub.

Wire protocol (server -> client), all frames are JSON text:
  * ``{"type": "snapshot", "data": <Snapshot>}``
      - sent once right after connect (current state from Redis, if any);
      - sent again on every engine update received on ``flowdesk:updates:{instrument}``.
  * ``{"type": "ping"}`` every 15s (heartbeat).

Client -> server:
  * ``{"type": "pong"}`` in reply to ping (any client frame is accepted/ignored;
    the receive loop exists mainly to observe pong and detect disconnect).

Feed-gap contract (for FE): when the upstream feed stalls, the engine keeps
emitting snapshots but with ``state == "STALE"`` and ``stale == true``. This WS
layer passes those frames through unchanged (no synthetic frames, no suppression).
The FE MUST hold/redraw the last good frame and surface a STALE badge until a
frame with ``stale == false`` arrives again.

Close codes:
  * ``4401`` — no session (unauthenticated).
  * ``4403`` — authenticated but missing the DESK role.
  * ``4400`` — bad/missing instrument (documented extension; not in TASK).
  * ``1011`` — live state store not configured (service unavailable).

The DESK gating reuses the same seam as the REST layer (``api.security``); Phase 3
replaces the cookie decoder with signed-cookie + Discord role verification without
touching this file.

The ``ConnectionManager`` keeps exactly one Redis subscription per instrument and
fans every decoded snapshot out to all connected client queues, so N browser tabs
share a single ``flowdesk:updates:{instrument}`` subscription. It depends only on
``asyncio`` and the state store's ``subscribe()`` API, so it is unit-testable
without a web stack.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional, Set

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from api.security import SESSION_COOKIE, parse_session_cookie

__all__ = [
    "WS_CLOSE_NO_SESSION",
    "WS_CLOSE_NO_DESK",
    "WS_CLOSE_BAD_INSTRUMENT",
    "WS_CLOSE_UNAVAILABLE",
    "DEFAULT_HEARTBEAT_S",
    "VALID_INSTRUMENTS",
    "heartbeat_interval_s",
    "ConnectionManager",
    "register_ws_routes",
]

# --------------------------------------------------------------------------- #
# Constants.                                                                   #
# --------------------------------------------------------------------------- #
WS_CLOSE_NO_SESSION = 4401
WS_CLOSE_NO_DESK = 4403
WS_CLOSE_BAD_INSTRUMENT = 4400
WS_CLOSE_UNAVAILABLE = 1011

DEFAULT_HEARTBEAT_S = 15.0

# Mirrors engine.schema.Instrument (Literal["ES", "NQ"]).
VALID_INSTRUMENTS = frozenset({"ES", "NQ"})


def heartbeat_interval_s() -> float:
    """Heartbeat period in seconds (env ``WS_HEARTBEAT_S``; default 15s).

    Read at connect time so tests can shrink it without rebuilding the app.
    """
    try:
        return float(os.environ.get("WS_HEARTBEAT_S", DEFAULT_HEARTBEAT_S))
    except (TypeError, ValueError):
        return DEFAULT_HEARTBEAT_S


# --------------------------------------------------------------------------- #
# Connection manager: one Redis subscription per instrument, fan-out to many.  #
# --------------------------------------------------------------------------- #
class _InstrumentHub:
    """Owns a single ``store.subscribe(instrument)`` and fans out to queues."""

    def __init__(self, store: Any, instrument: str) -> None:
        self._store = store
        self._instrument = instrument
        self._queues: Set["asyncio.Queue[dict[str, Any]]"] = set()
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def empty(self) -> bool:
        return not self._queues

    def add(self, queue: "asyncio.Queue[dict[str, Any]]") -> None:
        self._queues.add(queue)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    def remove(self, queue: "asyncio.Queue[dict[str, Any]]") -> None:
        self._queues.discard(queue)
        if not self._queues and self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        """Pump decoded snapshots from Redis pub/sub to every subscriber queue."""
        async with self._store.subscribe(self._instrument) as sub:
            async for snapshot in sub.messages():
                for queue in list(self._queues):
                    queue.put_nowait(snapshot)


class ConnectionManager:
    """Fan-out manager subscribing to ``flowdesk:updates:{instrument}``."""

    def __init__(self, store: Any) -> None:
        self._store = store
        self._hubs: dict[str, _InstrumentHub] = {}

    @property
    def store(self) -> Any:
        return self._store

    def _hub(self, instrument: str) -> _InstrumentHub:
        hub = self._hubs.get(instrument)
        if hub is None:
            hub = _InstrumentHub(self._store, instrument)
            self._hubs[instrument] = hub
        return hub

    @asynccontextmanager
    async def stream(self, instrument: str) -> AsyncIterator["asyncio.Queue[dict[str, Any]]"]:
        """Yield a queue that receives every snapshot for ``instrument``."""
        queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()
        hub = self._hub(instrument)
        hub.add(queue)
        try:
            yield queue
        finally:
            hub.remove(queue)
            if hub.empty:
                self._hubs.pop(instrument, None)


def _get_manager(app: Any, store: Any) -> ConnectionManager:
    """Cache one ConnectionManager per app, rebuilding if the store changed."""
    manager = getattr(app.state, "ws_manager", None)
    if manager is None or manager.store is not store:
        manager = ConnectionManager(store)
        app.state.ws_manager = manager
    return manager


# --------------------------------------------------------------------------- #
# Per-connection loops.                                                        #
# --------------------------------------------------------------------------- #
async def _push_loop(websocket: WebSocket, queue: "asyncio.Queue[dict[str, Any]]") -> None:
    """Forward fan-out snapshots to this client."""
    try:
        while True:
            snapshot = await queue.get()
            await websocket.send_json({"type": "snapshot", "data": snapshot})
    except WebSocketDisconnect:
        return


async def _heartbeat_loop(websocket: WebSocket) -> None:
    """Emit ``{type: ping}`` every heartbeat interval."""
    interval = heartbeat_interval_s()
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        return


async def _receive_loop(websocket: WebSocket) -> None:
    """Drain client frames (pong / control); completes on disconnect."""
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return


async def _safe_close(websocket: WebSocket, code: int = 1000) -> None:
    try:
        await websocket.close(code=code)
    except (RuntimeError, WebSocketDisconnect):
        pass


# --------------------------------------------------------------------------- #
# Endpoint handler.                                                            #
# --------------------------------------------------------------------------- #
async def serve(websocket: WebSocket, instrument: str) -> None:
    """DESK-gated WS handler: connect-snapshot, pub/sub push, heartbeat."""
    # --- gating BEFORE accept (PRD #8 AC-A5, T-09) ---
    session = parse_session_cookie(websocket.cookies.get(SESSION_COOKIE))
    if session is None:
        await websocket.close(code=WS_CLOSE_NO_SESSION)
        return
    if not session.has_desk:
        await websocket.close(code=WS_CLOSE_NO_DESK)
        return
    if instrument not in VALID_INSTRUMENTS:
        await websocket.close(code=WS_CLOSE_BAD_INSTRUMENT)
        return

    store = getattr(websocket.app.state, "state_store", None)
    if store is None:
        await websocket.close(code=WS_CLOSE_UNAVAILABLE)
        return

    await websocket.accept()

    # --- initial frame: current state (if any) ---
    current = await store.get_now(instrument)
    if current is not None:
        await websocket.send_json({"type": "snapshot", "data": current})

    # --- live stream + heartbeat + receive, until any task ends ---
    manager = _get_manager(websocket.app, store)
    async with manager.stream(instrument) as queue:
        tasks = [
            asyncio.create_task(_push_loop(websocket, queue)),
            asyncio.create_task(_heartbeat_loop(websocket)),
            asyncio.create_task(_receive_loop(websocket)),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except BaseException:  # noqa: BLE001 - shutdown best-effort
                    pass
            await _safe_close(websocket)


def register_ws_routes(app: FastAPI) -> None:
    """Register ``/ws`` on the FastAPI app."""

    @app.websocket("/ws")
    async def ws_stream(  # pragma: no cover - thin wrapper around serve()
        websocket: WebSocket, instrument: str = Query(...)
    ) -> None:
        await serve(websocket, instrument)
