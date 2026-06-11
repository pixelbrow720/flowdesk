"""FE auth contract (release 1.6): assert the /api/me shape per access_state.

Three layers, all network-free:

* **Core** — ``build_me_response`` mapping for ANON / NO_DESK / DESK / grace,
  plus the locked CTA. Runs without a web stack.
* **Fixtures** — the recorded JSON in ``mocks/`` parses into ``MeResponse`` and
  reports the documented ``access_state`` (the FE's offline data).
* **HTTP** — FastAPI ``TestClient`` confirms ``/api/me`` is public (ANON -> 200),
  reflects DESK/NO_DESK after a Discord callback, and that ``/api/me/recheck``
  forces a re-check. ``TestClient`` is imported lazily.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.auth_session import Session, end_of_day_et
from api.entitlement import (
    ACCESS_ANON,
    ACCESS_DESK,
    ACCESS_NO_DESK,
    BUY_URL,
    access_state_for,
    build_me_response,
)
from api.models import MeResponse

MOCKS = Path(__file__).resolve().parents[1] / "mocks"

DESK = "role-desk"
OTHER = "role-other"
NOW = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)  # 14:00 ET


# =========================================================================== #
# Core mapping                                                                #
# =========================================================================== #
def test_anon_shape() -> None:
    me = build_me_response(None, now=NOW)
    assert me.access_state == ACCESS_ANON
    assert me.discord_id is None
    assert me.has_desk is False and me.is_member is False
    assert me.last_checked is None and me.grace_until is None
    assert me.cta.buy_url == BUY_URL == "https://flowjob.id"
    assert me.cta.recheck_supported is True
    assert me.cta.join_url  # non-empty


def test_no_desk_shape() -> None:
    s = Session(discord_id="u1", has_desk=False, is_member=True,
                last_checked="2026-06-10T05:00:00Z")
    me = build_me_response(s, now=NOW)
    assert me.access_state == ACCESS_NO_DESK
    assert me.discord_id == "u1" and me.is_member is True and me.has_desk is False
    assert me.grace_until is None


def test_not_member_is_no_desk() -> None:
    s = Session(discord_id="u1", has_desk=False, is_member=False,
                last_checked="2026-06-10T05:00:00Z")
    assert access_state_for(s, now=NOW) == ACCESS_NO_DESK


def test_desk_shape() -> None:
    s = Session(discord_id="u1", has_desk=True, is_member=True,
                last_checked="2026-06-10T05:00:00Z")
    me = build_me_response(s, now=NOW)
    assert me.access_state == ACCESS_DESK and me.has_desk is True
    assert me.grace_until is None


def test_grace_is_desk_with_grace_until() -> None:
    grace = end_of_day_et(NOW).strftime("%Y-%m-%dT%H:%M:%SZ")
    s = Session(discord_id="u1", has_desk=False, is_member=True,
                last_checked=NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), grace_until=grace)
    me = build_me_response(s, now=NOW)
    assert me.access_state == ACCESS_DESK
    assert me.has_desk is False and me.grace_until == grace
    # after grace -> NO_DESK
    after = end_of_day_et(NOW) + timedelta(seconds=1)
    assert access_state_for(s, now=after) == ACCESS_NO_DESK


# =========================================================================== #
# Recorded fixtures (FE offline data)                                         #
# =========================================================================== #
def test_fixtures_match_models_and_states() -> None:
    expected = {
        "me_anon.json": ACCESS_ANON,
        "me_no_desk.json": ACCESS_NO_DESK,
        "me_desk.json": ACCESS_DESK,
        "me_grace.json": ACCESS_DESK,
    }
    for name, state in expected.items():
        raw = json.loads((MOCKS / name).read_text(encoding="utf-8"))
        me = MeResponse.model_validate(raw)  # parses against the contract
        assert me.access_state == state, name
        assert me.cta.buy_url == "https://flowjob.id", name
        assert me.cta.recheck_supported is True, name
    # the grace fixture must carry grace_until
    grace = MeResponse.model_validate(
        json.loads((MOCKS / "me_grace.json").read_text(encoding="utf-8"))
    )
    assert grace.grace_until is not None


# =========================================================================== #
# HTTP (FastAPI TestClient)                                                   #
# =========================================================================== #
SECRET = "test-secret-please-change"  # noqa: S105
GUILD = "guild-1"


def _env() -> None:
    os.environ["SESSION_SECRET"] = SECRET
    os.environ["DISCORD_GUILD_ID"] = GUILD
    os.environ["DISCORD_DESK_ROLE_ID"] = DESK
    os.environ["DISCORD_CLIENT_ID"] = "client-1"
    os.environ["DISCORD_CLIENT_SECRET"] = "client-secret"
    os.environ["CORS_ORIGINS"] = "https://app.flowdesk.test"
    os.environ["COOKIE_INSECURE"] = "1"


def _client(fake):
    from fastapi.testclient import TestClient

    _env()
    from api.main import create_app

    app = create_app()
    app.state.discord_client = fake
    return TestClient(app)


def _login_callback(client):
    from api.auth_session import OAUTH_STATE_COOKIE

    r = client.get("/api/auth/login", follow_redirects=False)
    assert r.status_code == 307
    state = client.cookies.get(OAUTH_STATE_COOKIE)
    return client.get("/api/auth/callback", params={"code": "c", "state": state},
                      follow_redirects=False)


def test_http_me_anonymous_is_200_anon() -> None:
    from api.discord_client import FakeDiscordClient

    client = _client(FakeDiscordClient())
    r = client.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["access_state"] == "ANON"
    assert body["discord_id"] is None
    assert body["cta"]["buy_url"] == "https://flowjob.id"
    assert body["cta"]["recheck_supported"] is True
    # recheck without a session -> 401
    assert client.post("/api/me/recheck").status_code == 401


def test_http_me_desk_after_callback() -> None:
    from api.discord_client import FakeDiscordClient

    fake = FakeDiscordClient(user_id="u-desk", token="tok")
    fake.set_roles((OTHER, DESK))
    client = _client(fake)
    _login_callback(client)
    body = client.get("/api/me").json()
    assert body["access_state"] == "DESK" and body["has_desk"] is True


def test_http_me_no_desk_after_callback() -> None:
    from api.discord_client import FakeDiscordClient

    fake = FakeDiscordClient(user_id="u-nodesk", token="tok")
    fake.set_roles((OTHER,))
    client = _client(fake)
    _login_callback(client)
    body = client.get("/api/me").json()
    assert body["access_state"] == "NO_DESK" and body["is_member"] is True
    # blocked at data endpoints
    assert client.get("/api/snapshot", params={"instrument": "ES"}).status_code == 403


def test_http_recheck_returns_me_shape() -> None:
    from api.discord_client import FakeDiscordClient

    fake = FakeDiscordClient(user_id="u-desk", token="tok")
    fake.set_roles((OTHER, DESK))
    client = _client(fake)
    _login_callback(client)
    fake.set_roles((OTHER,))  # revoke -> grace
    body = client.post("/api/me/recheck").json()
    assert body["access_state"] == "DESK"  # grace keeps full app today
    assert body["grace_until"] is not None
    assert "cta" in body and body["cta"]["buy_url"] == "https://flowjob.id"
