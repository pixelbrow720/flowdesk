"""FlowDesk — Redis-backed fixed-window rate limiter for hot auth/WS endpoints.

Phase 1 Item 2 hardening. Three endpoints are protected:

  * ``POST /api/me/recheck``           — forces a Discord guild-member fetch.
                                          Per-IP cap stops anonymous attackers
                                          from hammering Discord pre-session.
  * ``GET  /api/auth/discord/callback`` (and alias ``/api/auth/callback``)
                                       — limits OAuth callback floods.
  * ``WS   /ws``                       — limits handshake attempts before the
                                          cookie/session check.

Design notes
------------

* **Fixed-window counter**: Redis ``INCR`` on key ``rl:{scope}:{ident}:{window}``
  with ``EXPIRE`` set on first increment. Cheap, atomic, no Lua needed. Window
  size is fixed at 60 s; configurability is intentionally limited to keep the
  operational surface small.

* **Identity**: ``request.client.host`` by default. If ``RATE_LIMIT_TRUST_FORWARDED``
  is truthy (typically set to ``1`` in production behind a reverse proxy), the
  first IP from ``X-Forwarded-For`` is preferred. Off by default to prevent
  spoofing in dev / direct-exposure deployments.

* **Fail-open** on Redis errors: if the store is unreachable or raises, the
  request is allowed but the failure is logged at WARNING. Auth correctness
  must NOT depend on Redis availability — Redis hiccups should not lock users
  out.

* **Operational knobs** (Pilihan A; defaults safe, off the engine hot path):

      RATE_LIMIT_RECHECK_PER_MIN     default 6
      RATE_LIMIT_OAUTH_PER_MIN       default 10
      RATE_LIMIT_WS_PER_MIN          default 30
      RATE_LIMIT_TRUST_FORWARDED     default 0  (set to 1 behind a proxy)

  These are NOT part of the locked 12-key contract; they live in
  ``docs/02-locked-contract.md`` under the "Operational knobs" section.

The module exposes pure-ish functions plus a small ``RateLimiter`` wrapper so
the FastAPI layer can call ``await limiter.check(scope, request)`` and get back
a verdict tuple; HTTP/WS handlers decide how to surface the rejection (HTTP 429
with Retry-After vs. WS close 4429).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from api.errors import TooManyRequests

__all__ = [
    "RateLimiter",
    "RateLimitVerdict",
    "client_identity",
    "enforce_rate_limit",
    "rate_limit_key",
    "scope_limit",
    "WINDOW_SECONDS",
]

logger = logging.getLogger(__name__)

# Single fixed window. 60 s is the natural unit ("requests per minute") and
# keeps the key count bounded at 1 per (scope, ident) per minute.
WINDOW_SECONDS = 60

# Default per-minute caps. Overridable via env. Tuned conservatively:
# recheck/oauth are slow upstream calls (Discord); WS handshake is the cheapest.
_DEFAULTS = {
    "recheck": 6,            # 1 per 10 s — comfortable for a human, blocks scripts
    "oauth_callback": 10,    # OAuth callback is 1 per login attempt
    "ws_handshake": 30,      # WS reconnects can burst on flaky networks
}

_ENV_KEYS = {
    "recheck": "RATE_LIMIT_RECHECK_PER_MIN",
    "oauth_callback": "RATE_LIMIT_OAUTH_PER_MIN",
    "ws_handshake": "RATE_LIMIT_WS_PER_MIN",
}


@dataclass(frozen=True)
class RateLimitVerdict:
    """Outcome of a single ``check()`` call.

    ``allowed=True`` → handler proceeds. ``allowed=False`` → handler rejects with
    429 (HTTP) or close 1008 (WS). ``retry_after`` is the seconds the client
    should wait before retrying — always set when ``allowed=False``.
    """

    allowed: bool
    remaining: int
    retry_after: int
    scope: str
    ident: str


def scope_limit(scope: str) -> int:
    """Resolve the per-minute cap for a scope, honouring env overrides.

    Falls back to the default if the env var is missing, empty, non-integer,
    or non-positive. Bad config logs a WARNING but never crashes the app —
    rate-limit config is operational, not a contract value.
    """
    if scope not in _DEFAULTS:
        raise ValueError(f"unknown rate-limit scope: {scope!r}")
    raw = os.environ.get(_ENV_KEYS[scope], "").strip()
    if not raw:
        return _DEFAULTS[scope]
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%r (not an integer); using default %d",
            _ENV_KEYS[scope], raw, _DEFAULTS[scope],
        )
        return _DEFAULTS[scope]
    if value <= 0:
        logger.warning(
            "Invalid %s=%d (must be > 0); using default %d",
            _ENV_KEYS[scope], value, _DEFAULTS[scope],
        )
        return _DEFAULTS[scope]
    return value


def _trust_forwarded() -> bool:
    raw = os.environ.get("RATE_LIMIT_TRUST_FORWARDED", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def client_identity(request_or_ws: Any) -> str:
    """Extract a stable client identifier (IP) from a Request or WebSocket.

    Prefers ``X-Forwarded-For`` (first hop) iff ``RATE_LIMIT_TRUST_FORWARDED``
    is set; otherwise uses ``client.host``. Falls back to the literal string
    ``"unknown"`` if neither is available — that bucket gets its own quota,
    which is the safe default (a flood from unknown sources still gets capped).
    """
    headers = getattr(request_or_ws, "headers", None)
    if _trust_forwarded() and headers is not None:
        xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    client = getattr(request_or_ws, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return host or "unknown"


def rate_limit_key(scope: str, ident: str, *, now: Optional[float] = None) -> str:
    """Compose the Redis key for a (scope, ident) bucket in the current window.

    Window is keyed by the integer ``floor(now / WINDOW_SECONDS)`` so two
    requests in the same minute hit the same counter. Exposed for tests.
    """
    ts = time.time() if now is None else now
    window = int(ts // WINDOW_SECONDS)
    return f"rl:{scope}:{ident}:{window}"


class RateLimiter:
    """Thin async wrapper around a redis-py asyncio client.

    The client is supplied (not constructed) so tests can pass a ``fakeredis``
    instance and production code can pass the same client used by ``StateStore``.
    A ``None`` client means "Redis disabled" — every check fails open.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def check(self, scope: str, request_or_ws: Any) -> RateLimitVerdict:
        """Increment the counter and decide whether to allow the request.

        Always returns a verdict; never raises on Redis failure (fail-open).
        """
        ident = client_identity(request_or_ws)
        limit = scope_limit(scope)

        if self._client is None:
            # Redis disabled (e.g. local dev without REDIS_URL). Allow but log
            # once per process at INFO so operators notice if prod hits this.
            return RateLimitVerdict(
                allowed=True, remaining=limit, retry_after=0,
                scope=scope, ident=ident,
            )

        now = time.time()
        key = rate_limit_key(scope, ident, now=now)
        try:
            count = await self._client.incr(key)
            if count == 1:
                # Set TTL only on first hit. 2× window so a request landing at
                # the very end of a window still has a TTL covering the next
                # window's lookups in pathological clock-skew cases.
                await self._client.expire(key, WINDOW_SECONDS * 2)
        except Exception as exc:  # noqa: BLE001 — fail-open is the contract
            logger.warning(
                "Rate limiter Redis error (scope=%s ident=%s): %s; failing open",
                scope, ident, exc,
            )
            return RateLimitVerdict(
                allowed=True, remaining=limit, retry_after=0,
                scope=scope, ident=ident,
            )

        if count > limit:
            # Seconds remaining in the current window — that's how long until
            # the counter resets. Always >= 1 to satisfy Retry-After's integer
            # semantics ("0" would mean "retry now", which is wrong).
            elapsed_in_window = now % WINDOW_SECONDS
            retry_after = max(1, int(WINDOW_SECONDS - elapsed_in_window))
            return RateLimitVerdict(
                allowed=False, remaining=0, retry_after=retry_after,
                scope=scope, ident=ident,
            )

        return RateLimitVerdict(
            allowed=True, remaining=limit - count, retry_after=0,
            scope=scope, ident=ident,
        )


async def enforce_rate_limit(scope: str, request: Any) -> None:
    """Check the rate limit for ``scope`` against ``request.client.host``.

    Raises :class:`~api.errors.TooManyRequests` (HTTP 429 + ``Retry-After``)
    when the caller is over budget. No-op when no limiter is wired
    (dev / no-Redis): the limiter itself fails open, so this stays consistent.

    Lives here (not in ``api.main``) so both ``api.main`` and ``api.auth`` can
    import it at top level without the historical main<->auth import cycle.
    """
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return
    verdict = await limiter.check(scope, request)
    if not verdict.allowed:
        raise TooManyRequests(
            f"rate limit exceeded for {scope}",
            retry_after=verdict.retry_after,
        )
