"""FlowDesk — Redis "current state" layer (live now-state + WS pub/sub fan-out).

This is the LIVE side of the data path (PRD #8 §5, §13): the engine worker writes
the latest snapshot per instrument to Redis and publishes it; the API WebSocket
layer subscribes and fans messages out to connected clients. Replay reads come
from TimescaleDB instead (see ``db/repo.py``).

Key scheme (see also README; documented as constants so it is trivial to swap):

    flowdesk:now:{instrument}      STRING  -> latest snapshot JSON (string)
    flowdesk:session:{instrument}  STRING  -> current session state (e.g. "LIVE")
    flowdesk:updates:{instrument}  CHANNEL -> pub/sub, latest snapshot JSON per tick

NOTE: PRD #8 §5 spells these as ``state:{instrument}:latest`` /
``state:{instrument}:session`` / channel ``live:{instrument}``. This module follows
the (more specific) build-task scheme above; flip the constants below to restore
the PRD literal names if desired. Redis key names are NOT part of the locked
contract.

redis-py is imported lazily (only in :func:`create_client`) so this module — and
the test suite using fakeredis — import cleanly without a live Redis server.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Mapping, Optional

__all__ = [
    "NOW_KEY",
    "SESSION_KEY",
    "UPDATES_CHANNEL",
    "now_key",
    "session_key",
    "updates_channel",
    "StateStore",
    "Subscription",
    "create_client",
    "create_state_store",
]

# --------------------------------------------------------------------------- #
# Key scheme (single source of truth).                                         #
# --------------------------------------------------------------------------- #
NOW_KEY = "flowdesk:now:{instrument}"
SESSION_KEY = "flowdesk:session:{instrument}"
UPDATES_CHANNEL = "flowdesk:updates:{instrument}"


def now_key(instrument: str) -> str:
    """Redis STRING key holding the latest snapshot JSON for an instrument."""
    return NOW_KEY.format(instrument=instrument)


def session_key(instrument: str) -> str:
    """Redis STRING key holding the current session state for an instrument."""
    return SESSION_KEY.format(instrument=instrument)


def updates_channel(instrument: str) -> str:
    """Pub/sub channel used to fan out per-minute snapshots to the WS layer."""
    return UPDATES_CHANNEL.format(instrument=instrument)


# --------------------------------------------------------------------------- #
# Encoding helpers.                                                            #
# --------------------------------------------------------------------------- #
def _to_json(snapshot: Any) -> str:
    """Normalise a snapshot (mapping / JSON string / pydantic model) to JSON."""
    if isinstance(snapshot, (str, bytes, bytearray)):
        # Validate it is JSON, then return a canonical compact string.
        return json.dumps(json.loads(snapshot), separators=(",", ":"))
    model_dump = getattr(snapshot, "model_dump", None)
    if callable(model_dump):
        return json.dumps(model_dump(), separators=(",", ":"))
    if isinstance(snapshot, Mapping):
        return json.dumps(dict(snapshot), separators=(",", ":"))
    raise TypeError(f"unsupported snapshot type: {type(snapshot)!r}")


def _decode_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, Mapping):
        return dict(raw)
    raise TypeError(f"unexpected value type from Redis: {type(raw)!r}")


def _decode_str(raw: Any) -> str:
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8")
    return str(raw)


# --------------------------------------------------------------------------- #
# Subscription helper for the WebSocket layer.                                 #
# --------------------------------------------------------------------------- #
class Subscription:
    """Async context manager + iterator over snapshots for one instrument.

    Usage (WS layer)::

        async with store.subscribe("ES") as sub:
            async for snapshot in sub.messages():
                await websocket.send_json({"type": "snapshot", "data": snapshot})
    """

    def __init__(self, client: Any, instrument: str) -> None:
        self._client = client
        self._instrument = instrument
        self._channel = updates_channel(instrument)
        self._pubsub: Any = None

    async def __aenter__(self) -> "Subscription":
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(self._channel)
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(self._channel)
            finally:
                # redis-py 5 prefers aclose(); fall back to close() for older.
                aclose = getattr(self._pubsub, "aclose", None)
                if aclose is not None:
                    await aclose()
                else:
                    res = self._pubsub.close()
                    if hasattr(res, "__await__"):
                        await res
            self._pubsub = None
        return False

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded snapshot payloads (skips subscribe/control frames)."""
        if self._pubsub is None:
            raise RuntimeError("Subscription used outside 'async with' block")
        async for message in self._pubsub.listen():
            if message is None:
                continue
            if message.get("type") == "message":
                yield _decode_json(message["data"])


# --------------------------------------------------------------------------- #
# State store.                                                                 #
# --------------------------------------------------------------------------- #
class StateStore:
    """Thin wrapper over a redis-py asyncio client for the live now-state."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        return self._client

    async def set_now(self, instrument: str, snapshot: Any) -> str:
        """Store the latest snapshot AND publish it to the updates channel.

        Returns the JSON string that was stored/published.
        """
        payload = _to_json(snapshot)
        await self._client.set(now_key(instrument), payload)
        await self._client.publish(updates_channel(instrument), payload)
        return payload

    async def get_now(self, instrument: str) -> Optional[dict[str, Any]]:
        """Return the latest snapshot payload, or None if not set yet."""
        raw = await self._client.get(now_key(instrument))
        if raw is None:
            return None
        return _decode_json(raw)

    async def set_session(self, instrument: str, state: str) -> None:
        """Store the current session state string (PRD #9 SessionState)."""
        await self._client.set(session_key(instrument), str(state))

    async def get_session(self, instrument: str) -> Optional[str]:
        """Return the current session state string, or None if unset."""
        raw = await self._client.get(session_key(instrument))
        if raw is None:
            return None
        return _decode_str(raw)

    def subscribe(self, instrument: str) -> Subscription:
        """Return a Subscription async-context-manager for the WS layer."""
        return Subscription(self._client, instrument)


# --------------------------------------------------------------------------- #
# Factories (redis-py imported lazily).                                        #
# --------------------------------------------------------------------------- #
def create_client(url: str) -> Any:
    """Create a redis-py asyncio client from REDIS_URL (strings decoded)."""
    import redis.asyncio as redis  # local import: optional at module load time

    return redis.from_url(url, encoding="utf-8", decode_responses=True)


def create_state_store(url: str) -> StateStore:
    """Convenience: build a StateStore backed by a real Redis connection."""
    return StateStore(create_client(url))
