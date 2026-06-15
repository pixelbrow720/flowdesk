"""Integration tests: rate limiter wired into the 3 hot endpoints.

Verifies that the limiter is actually invoked (and surfaces correctly) at:

* ``POST /api/me/recheck``               → HTTP 429 + ``Retry-After``
* ``GET  /api/auth/discord/callback``    → HTTP 429 + ``Retry-After``
* ``WS   /ws``                            → close code ``WS_CLOSE_RATE_LIMITED``

Each test pins per-minute caps to 1 via env so the second hit always trips.
The limiter is constructed from a fresh ``fakeredis.aioredis`` instance and
attached to ``app.state.rate_limiter`` post-startup, mirroring the lifespan
wiring path without requiring REDIS_URL.

Network-free: Discord client is the in-memory ``FakeDiscordClient``, Redis is
``fakeredis``. These tests must NOT need a live Redis or Discord.
"""
from __future__ import annotations

import fakeredis.aioredis
import pytest

from api.discord_client import FakeDiscordClient
from api.rate_limit import RateLimiter
from api.ws import WS_CLOSE_RATE_LIMITED

SECRET = "test-secret-please-change"
GUILD = "guild-1"
DESK = "role-desk"


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", SECRET)
    monkeypatch.setenv("DISCORD_GUILD_ID", GUILD)
    monkeypatch.setenv("DISCORD_DESK_ROLE_ID", DESK)
    monkeypatch.setenv("DISCORD_CLIENT_ID", "client-1")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.flowdesk.test")
    monkeypatch.setenv("COOKIES_INSECURE", "1")
    # Pin every cap to 1/min so the second hit in the same window always trips.
    monkeypatch.setenv("RATE_LIMIT_RECHECK_PER_MIN", "1")
    monkeypatch.setenv("RATE_LIMIT_OAUTH_PER_MIN", "1")
    monkeypatch.setenv("RATE_LIMIT_WS_PER_MIN", "1")


def _make_client(fake: FakeDiscordClient):
    """Build a TestClient with limiter wired and Discord faked."""
    from fastapi.testclient import TestClient

    from api.main import create_app

    app = create_app()
    app.state.discord_client = fake
    app.state.rate_limiter = RateLimiter(fakeredis.aioredis.FakeRedis(decode_responses=True))
    return TestClient(app)


# --------------------------------------------------------------------------- #
# /api/me/recheck                                                             #
# --------------------------------------------------------------------------- #
def test_recheck_rate_limited_returns_429_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    client = _make_client(FakeDiscordClient())
    # First call: anonymous → 401 (auth check still runs, but limiter saw 1 hit).
    r1 = client.post("/api/me/recheck")
    assert r1.status_code == 401
    # Second call from the same client (same IP) → tripped by limiter BEFORE auth.
    r2 = client.post("/api/me/recheck")
    assert r2.status_code == 429, r2.text
    # Retry-After header is set to the integer seconds remaining in the window.
    retry_after = r2.headers.get("Retry-After")
    assert retry_after is not None and int(retry_after) >= 1
    body = r2.json()
    assert body["code"] == "RATE_LIMITED"
    assert isinstance(body["error"], str) and "rate limit" in body["error"].lower()


# --------------------------------------------------------------------------- #
# /api/auth/discord/callback                                                  #
# --------------------------------------------------------------------------- #
def test_oauth_callback_rate_limited_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    client = _make_client(FakeDiscordClient())
    # First: junk callback → 400 BAD_REQUEST (CSRF check), but limiter saw 1 hit.
    r1 = client.get("/api/auth/discord/callback", params={"code": "x", "state": "y"})
    assert r1.status_code == 400
    # Second: tripped before CSRF/Discord work happens.
    r2 = client.get("/api/auth/discord/callback", params={"code": "x", "state": "y"})
    assert r2.status_code == 429, r2.text
    assert int(r2.headers["Retry-After"]) >= 1
    assert r2.json()["code"] == "RATE_LIMITED"


# --------------------------------------------------------------------------- #
# WS /ws handshake                                                            #
# --------------------------------------------------------------------------- #
def test_ws_handshake_rate_limited_closes_with_4429(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    client = _make_client(FakeDiscordClient())
    from starlette.websockets import WebSocketDisconnect

    # First WS attempt: no session cookie → server closes pre-accept with 4401
    # (NO_SESSION). Starlette's TestClient raises WebSocketDisconnect from the
    # context manager's __enter__ in that case, so we don't reach the body.
    # Limiter still saw 1 hit.
    with pytest.raises(WebSocketDisconnect) as exc1:  # noqa: SIM117 — readability over combined-with
        with client.websocket_connect("/ws?instrument=ES"):
            pass
    assert exc1.value.code in (4401, 4403), f"unexpected first-close code {exc1.value.code}"

    # Second WS attempt from the same client → tripped by limiter BEFORE cookie work.
    with pytest.raises(WebSocketDisconnect) as exc2:  # noqa: SIM117 — readability over combined-with
        with client.websocket_connect("/ws?instrument=ES"):
            pass
    assert exc2.value.code == WS_CLOSE_RATE_LIMITED, (
        f"expected close {WS_CLOSE_RATE_LIMITED}, got {exc2.value.code}"
    )
