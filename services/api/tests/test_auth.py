"""T-09: Discord OAuth2 + session gating (PRD #6).

Two layers, all network-free (FakeDiscordClient):

* **Core** (no web stack): the signed cookie round-trip, the ``check_access``
  gating algorithm, the ET grace computation, and exact cookie flags. These run
  anywhere (used for the sandbox proof).
* **HTTP** (FastAPI ``TestClient``): the real routes -- login redirect, callback
  happy/no-DESK paths, logout, /api/me, /api/me/recheck, and the
  non-DESK-blocked-at-data-endpoints acceptance. ``TestClient`` is imported
  lazily so this module imports even where FastAPI is absent.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from api.auth_session import (
    ET,
    OAUTH_STATE_COOKIE,
    SESSION_COOKIE,
    Access,
    Session,
    check_access,
    deserialize_session,
    end_of_day_et,
    serialize_session,
    set_session_cookie,
)
from api.discord_client import FakeDiscordClient, GuildMember
from api.security import has_active_grace, require_desk
from api.errors import Forbidden, Unauthenticated

SECRET = "test-secret-please-change"  # noqa: S105 - test-only, not from prod
GUILD = "guild-1"
DESK = "role-desk"
OTHER = "role-other"


def _env() -> None:
    os.environ["SESSION_SECRET"] = SECRET
    os.environ["DISCORD_GUILD_ID"] = GUILD
    os.environ["DISCORD_DESK_ROLE_ID"] = DESK
    os.environ["DISCORD_CLIENT_ID"] = "client-1"
    os.environ["DISCORD_CLIENT_SECRET"] = "client-secret"
    os.environ["CORS_ORIGINS"] = "https://app.flowdesk.test"


# =========================================================================== #
# Core (no web stack)                                                         #
# =========================================================================== #
def test_signed_cookie_roundtrip_and_tamper() -> None:
    s = Session(discord_id="u1", has_desk=True, is_member=True, last_checked="2026-06-10T13:00:00Z")
    token = serialize_session(s, SECRET)
    back = deserialize_session(token, SECRET)
    assert back is not None and back.discord_id == "u1" and back.has_desk is True
    # tampered signature -> None
    assert deserialize_session(token[:-2] + "xx", SECRET) is None
    # wrong secret -> None
    assert deserialize_session(token, "other-secret") is None
    # expired -> None
    past = datetime.now(timezone.utc) - timedelta(days=8)
    expired = serialize_session(s, SECRET, now=past)
    assert deserialize_session(expired, SECRET) is None


def test_session_token_is_encrypted_not_readable() -> None:  # IMPORTANT #3 regression
    # The Discord access_token must NOT be recoverable from the cookie without the
    # secret. Before encryption it was base64-decodable from the HMAC-signed body.
    import base64

    sentinel = "DISCORD-BEARER-SENTINEL-9f3a"
    s = Session(
        discord_id="u1", has_desk=True, is_member=True, access_token=sentinel
    )
    token = serialize_session(s, SECRET)
    # round-trips correctly with the secret
    back = deserialize_session(token, SECRET)
    assert back is not None and back.access_token == sentinel
    # but the token is NOT present in plaintext, nor via a naive base64 decode
    assert sentinel not in token
    pad = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(token + pad)
    except Exception:
        decoded = b""
    assert sentinel.encode() not in decoded


def test_legacy_signed_cookie_rejected() -> None:  # IMPORTANT #3 back-compat
    # A pre-encryption HMAC-signed cookie must deserialize to None (force re-login),
    # NOT crash. Builds the old format via the still-present sign_value.
    from api.auth_session import sign_value

    s = Session(discord_id="u1", has_desk=True, is_member=True)
    payload = s.model_dump()
    payload["exp"] = datetime.now(timezone.utc).timestamp() + 1000
    legacy = sign_value(payload, SECRET)  # old body.sig format
    assert deserialize_session(legacy, SECRET) is None


def test_cookie_flags_exact() -> None:
    class _Resp:
        def __init__(self) -> None:
            self.kw: dict = {}

        def set_cookie(self, **kw: object) -> None:
            self.kw = kw

    r = _Resp()
    set_session_cookie(r, "value", secure=True)
    assert r.kw["key"] == SESSION_COOKIE
    assert r.kw["httponly"] is True
    assert r.kw["secure"] is True
    assert r.kw["samesite"] == "lax"
    assert r.kw["max_age"] == 7 * 24 * 60 * 60
    assert r.kw["path"] == "/"


def test_end_of_day_et_is_next_et_midnight() -> None:
    # 2026-06-10 18:00 UTC == 14:00 ET (EDT). EOD ET == 2026-06-11 00:00 ET == 04:00 UTC.
    now = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)
    eod = end_of_day_et(now)
    assert eod == datetime(2026, 6, 11, 4, 0, tzinfo=timezone.utc)
    # In ET it is exactly next midnight.
    assert eod.astimezone(ET).hour == 0 and eod.astimezone(ET).day == 11


def test_check_access_happy_desk() -> None:
    s = Session(discord_id="u1", last_checked=None)
    member = GuildMember(roles=(OTHER, DESK))
    res = check_access(s, member=member, desk_role_id=DESK, force=True)
    assert res.decision is Access.ALLOW and res.session.has_desk is True
    assert res.session.grace_until is None and res.changed is True


def test_check_access_no_desk_denied() -> None:
    s = Session(discord_id="u1", last_checked=None)
    member = GuildMember(roles=(OTHER,))
    res = check_access(s, member=member, desk_role_id=DESK, force=True)
    assert res.decision is Access.DENY_NO_DESK
    # never-DESK user gets NO grace
    assert res.session.grace_until is None


def test_check_access_not_member_denied() -> None:
    s = Session(discord_id="u1", last_checked=None)
    res = check_access(s, member=None, desk_role_id=DESK, force=True)
    assert res.decision is Access.DENY_NOT_MEMBER and res.session.is_member is False


def test_revocation_starts_grace_then_expires() -> None:
    now = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)  # 14:00 ET
    # Had DESK, now revoked (still a member, role gone) -> grace until EOD ET.
    s = Session(discord_id="u1", has_desk=True, is_member=True,
                last_checked=(now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    member = GuildMember(roles=(OTHER,))
    res = check_access(s, now=now, member=member, desk_role_id=DESK)
    assert res.decision is Access.ALLOW_GRACE
    assert res.session.has_desk is False and res.session.grace_until is not None
    # require_desk allows during grace ...
    require_desk(res.session, now=now)
    assert has_active_grace(res.session, now=now) is True
    # ... but after grace end (next day), access is forbidden.
    after = end_of_day_et(now) + timedelta(seconds=1)
    assert has_active_grace(res.session, now=after) is False
    try:
        require_desk(res.session, now=after)
    except Forbidden:
        pass
    else:
        raise AssertionError("expected Forbidden after grace")


def test_recheck_not_due_keeps_cache() -> None:
    now = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)
    s = Session(discord_id="u1", has_desk=True, is_member=True,
                last_checked=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    # Not forced, checked just now -> no re-check, no change even if member given.
    res = check_access(s, now=now, member=GuildMember(roles=(OTHER,)), desk_role_id=DESK)
    assert res.changed is False and res.decision is Access.ALLOW


def test_discord_unavailable_keeps_cache() -> None:
    now = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)
    s = Session(discord_id="u1", has_desk=True, is_member=True,
                last_checked=(now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    # Sentinel default member (...) == "no re-check performed / Discord down".
    res = check_access(s, now=now, desk_role_id=DESK, force=True)
    assert res.changed is False and res.decision is Access.ALLOW


def test_require_desk_401_403() -> None:
    try:
        require_desk(None)
    except Unauthenticated:
        pass
    else:
        raise AssertionError("expected Unauthenticated for no session")
    try:
        require_desk(Session(discord_id="u1", has_desk=False, is_member=True))
    except Forbidden:
        pass
    else:
        raise AssertionError("expected Forbidden for no-DESK session")


# =========================================================================== #
# HTTP (FastAPI TestClient)                                                   #
# =========================================================================== #
def _make_client(fake: FakeDiscordClient, *, insecure: bool = True):
    """Build a TestClient with the fake Discord client injected."""
    from fastapi.testclient import TestClient

    _env()
    if insecure:
        os.environ["COOKIE_INSECURE"] = "1"
    else:
        os.environ.pop("COOKIE_INSECURE", None)
    from api.main import create_app

    app = create_app()
    app.state.discord_client = fake
    return TestClient(app)


def _do_login_callback(client, code: str = "auth-code"):
    r = client.get("/api/auth/login", follow_redirects=False)
    assert r.status_code == 307
    assert "discord.com/oauth2/authorize" in r.headers["location"]
    state = client.cookies.get(OAUTH_STATE_COOKIE)
    assert state
    return client.get(
        "/api/auth/callback", params={"code": code, "state": state},
        follow_redirects=False,
    )


def test_http_callback_happy_desk() -> None:
    fake = FakeDiscordClient(user_id="u-desk", token="tok1")
    fake.set_roles((OTHER, DESK))
    client = _make_client(fake)
    r = _do_login_callback(client)
    assert r.status_code == 307
    cookie = client.cookies.get(SESSION_COOKIE)
    assert cookie
    sess = deserialize_session(cookie, SECRET)
    assert sess and sess.discord_id == "u-desk" and sess.has_desk is True
    # DESK can hit /api/me
    me = client.get("/api/me")
    assert me.status_code == 200 and me.json()["has_desk"] is True


def test_http_callback_no_desk_blocked_at_data_endpoints() -> None:
    fake = FakeDiscordClient(user_id="u-nodesk", token="tok2")
    fake.set_roles((OTHER,))  # member, but no DESK
    client = _make_client(fake)
    r = _do_login_callback(client)
    assert r.status_code == 307
    # T-09: non-DESK blocked at data endpoints -> 403
    snap = client.get("/api/snapshot", params={"instrument": "ES"})
    assert snap.status_code == 403
    rep = client.get("/api/replay/sessions", params={"instrument": "ES"})
    assert rep.status_code == 403
    # /api/me still works (auth, not DESK-gated)
    me = client.get("/api/me")
    assert me.status_code == 200 and me.json()["has_desk"] is False


def test_http_unauthenticated_is_401() -> None:
    fake = FakeDiscordClient()
    client = _make_client(fake)
    assert client.get("/api/snapshot", params={"instrument": "ES"}).status_code == 401
    # /api/me is PUBLIC (release 1.6): anonymous -> 200 ANON, not 401.
    me = client.get("/api/me")
    assert me.status_code == 200 and me.json()["access_state"] == "ANON"
    # recheck still requires a session.
    assert client.post("/api/me/recheck").status_code == 401


def test_http_recheck_forces_discord_call() -> None:
    fake = FakeDiscordClient(user_id="u-desk", token="tok3")
    fake.set_roles((OTHER, DESK))
    client = _make_client(fake)
    _do_login_callback(client)
    calls_before = list(fake.calls)
    # Revoke DESK then force a re-check.
    fake.set_roles((OTHER,))
    r = client.post("/api/me/recheck")
    assert r.status_code == 200
    body = r.json()
    # role revoked -> grace, still allowed today, has_desk now False
    assert body["has_desk"] is False
    assert body["grace_until"] is not None
    assert fake.calls.count("fetch_member") > calls_before.count("fetch_member")


def test_http_logout_clears_cookie() -> None:
    fake = FakeDiscordClient(user_id="u-desk", token="tok4")
    fake.set_roles((OTHER, DESK))
    client = _make_client(fake)
    _do_login_callback(client)
    assert client.cookies.get(SESSION_COOKIE)
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    # Set-Cookie clears it (empty value / expired).
    assert 'flowdesk_session=""' in r.headers.get("set-cookie", "") or \
        "flowdesk_session=;" in r.headers.get("set-cookie", "")


def test_http_cookie_flags_secure_when_not_insecure() -> None:
    fake = FakeDiscordClient(user_id="u-desk", token="tok5")
    fake.set_roles((OTHER, DESK))
    client = _make_client(fake, insecure=False)
    r = client.get("/api/auth/login", follow_redirects=False)
    set_cookie = r.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    # SameSite value is case-insensitive (RFC 6265bis); Starlette emits "lax".
    assert "samesite=lax" in set_cookie.lower()
