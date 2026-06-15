"""Tests for the Redis-backed rate limiter (Phase 1 Item 2).

Uses ``fakeredis.aioredis`` (already in dev deps for ``test_state.py``) so no
real Redis is needed. Time is patched via ``unittest.mock`` on
``api.rate_limit.time.time`` to deterministically test window-roll behaviour.

Convention: async tests run via ``asyncio.run`` to match ``test_state.py`` —
the suite stays plugin-free (no pytest-asyncio dep).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import fakeredis.aioredis
import pytest

from api.rate_limit import (
    RateLimiter,
    WINDOW_SECONDS,
    client_identity,
    rate_limit_key,
    scope_limit,
)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _request(host: str = "1.2.3.4", xff: str | None = None) -> Any:
    """Minimal Request-like object: ``.client.host`` + ``.headers.get()``."""
    headers: dict[str, str] = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff

    class _Headers:
        def get(self, key: str, default: Any = None) -> Any:
            return headers.get(key.lower(), default)

    return SimpleNamespace(client=SimpleNamespace(host=host), headers=_Headers())


def _fake_redis() -> Any:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# --------------------------------------------------------------------------- #
# scope_limit() — env override resolution (sync, no Redis)                     #
# --------------------------------------------------------------------------- #
def test_scope_limit_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("RATE_LIMIT_RECHECK_PER_MIN",
                "RATE_LIMIT_OAUTH_PER_MIN",
                "RATE_LIMIT_WS_PER_MIN"):
        monkeypatch.delenv(var, raising=False)
    assert scope_limit("recheck") == 6
    assert scope_limit("oauth_callback") == 10
    assert scope_limit("ws_handshake") == 30


def test_scope_limit_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "2")
    assert scope_limit("recheck") == 2


def test_scope_limit_invalid_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "not-a-number")
    assert scope_limit("recheck") == 6  # default

    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "0")
    assert scope_limit("recheck") == 6  # non-positive rejected

    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "-5")
    assert scope_limit("recheck") == 6


def test_scope_limit_unknown_scope_raises() -> None:
    with pytest.raises(ValueError, match="unknown rate-limit scope"):
        scope_limit("nope")


# --------------------------------------------------------------------------- #
# client_identity() — IP extraction with/without TRUST_FORWARDED               #
# --------------------------------------------------------------------------- #
def test_client_identity_uses_client_host_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RATE_LIMIT_TRUST_FORWARDED", raising=False)
    req = _request(host="10.0.0.1", xff="evil.spoof, 8.8.8.8")
    assert client_identity(req) == "10.0.0.1"  # XFF ignored


def test_client_identity_honours_trust_forwarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_TRUST_FORWARDED", "1")
    req = _request(host="10.0.0.1", xff="203.0.113.7, 8.8.8.8")
    assert client_identity(req) == "203.0.113.7"  # first XFF hop


def test_client_identity_falls_back_when_unknown() -> None:
    req = SimpleNamespace(client=None, headers=None)
    assert client_identity(req) == "unknown"


# --------------------------------------------------------------------------- #
# rate_limit_key()                                                             #
# --------------------------------------------------------------------------- #
def test_rate_limit_key_shape() -> None:
    key = rate_limit_key("recheck", "1.2.3.4", now=1000.0)
    assert key.startswith("rl:recheck:1.2.3.4:")
    assert key.endswith(":16")  # 1000 // 60 == 16


def test_rate_limit_key_window_changes_at_boundary() -> None:
    k1 = rate_limit_key("recheck", "x", now=59.999)
    k2 = rate_limit_key("recheck", "x", now=60.0)
    assert k1 != k2


# --------------------------------------------------------------------------- #
# RateLimiter — async behaviour (driven via asyncio.run)                       #
# --------------------------------------------------------------------------- #
def test_disabled_limiter_always_allows() -> None:
    async def run() -> None:
        limiter = RateLimiter(client=None)
        assert not limiter.enabled
        for _ in range(100):
            v = await limiter.check("recheck", _request())
            assert v.allowed
            assert v.retry_after == 0

    asyncio.run(run())


def test_under_limit_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "3")

    async def run() -> None:
        client = _fake_redis()
        try:
            limiter = RateLimiter(client=client)
            req = _request(host="1.1.1.1")
            for i in range(3):
                v = await limiter.check("recheck", req)
                assert v.allowed, f"hit {i+1} should be allowed"
                assert v.remaining == 2 - i
        finally:
            await client.aclose()

    asyncio.run(run())


def test_over_limit_denies_with_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "2")

    async def run() -> None:
        client = _fake_redis()
        try:
            limiter = RateLimiter(client=client)
            req = _request(host="2.2.2.2")
            assert (await limiter.check("recheck", req)).allowed
            assert (await limiter.check("recheck", req)).allowed
            v = await limiter.check("recheck", req)
            assert not v.allowed
            assert v.remaining == 0
            assert 1 <= v.retry_after <= WINDOW_SECONDS
        finally:
            await client.aclose()

    asyncio.run(run())


def test_window_roll_resets_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "1")

    async def run() -> None:
        client = _fake_redis()
        try:
            limiter = RateLimiter(client=client)
            req = _request(host="3.3.3.3")

            with patch("api.rate_limit.time.time", return_value=1000.0):
                assert (await limiter.check("recheck", req)).allowed
                assert not (await limiter.check("recheck", req)).allowed

            # Jump to next window — counter resets
            with patch(
                "api.rate_limit.time.time",
                return_value=1000.0 + WINDOW_SECONDS,
            ):
                assert (await limiter.check("recheck", req)).allowed
        finally:
            await client.aclose()

    asyncio.run(run())


def test_per_ip_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "1")

    async def run() -> None:
        client = _fake_redis()
        try:
            limiter = RateLimiter(client=client)
            req_a = _request(host="4.4.4.4")
            req_b = _request(host="5.5.5.5")

            assert (await limiter.check("recheck", req_a)).allowed
            assert not (await limiter.check("recheck", req_a)).allowed
            assert (await limiter.check("recheck", req_b)).allowed  # other IP
        finally:
            await client.aclose()

    asyncio.run(run())


def test_per_scope_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "1")
    monkeypatch.setenv("RATE_LIMIT_OAUTH_PER_MIN", "1")

    async def run() -> None:
        client = _fake_redis()
        try:
            limiter = RateLimiter(client=client)
            req = _request(host="6.6.6.6")

            assert (await limiter.check("recheck", req)).allowed
            assert not (await limiter.check("recheck", req)).allowed
            # Same IP, different scope — independent bucket
            assert (await limiter.check("oauth_callback", req)).allowed
        finally:
            await client.aclose()

    asyncio.run(run())


def test_redis_error_fails_open() -> None:
    """If Redis raises, allow the request (don't break auth on Redis hiccup)."""

    class BrokenRedis:
        async def incr(self, key: str) -> int:
            raise ConnectionError("boom")

        async def expire(self, key: str, ttl: int) -> bool:  # pragma: no cover
            return True

    async def run() -> None:
        limiter = RateLimiter(client=BrokenRedis())
        v = await limiter.check("recheck", _request())
        assert v.allowed, "Redis failure must fail-open, not lock users out"

    asyncio.run(run())
