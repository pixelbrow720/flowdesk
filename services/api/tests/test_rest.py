"""REST API tests — FastAPI TestClient with mocked repo + state.

Covers 200 / 401 / 403 / 404 / 422 across the PRD #8 §6 contract, and the DESK
gating seam (T-09: non-DESK -> 403). Backends are injected via dependency
overrides; auth is simulated with a SIGNED session cookie (the release-1.5+
HMAC scheme — see api/auth_session.serialize_session), and ``/api/me`` is PUBLIC
per the release-1.6 FE auth contract (anonymous -> 200 ANON, not 401).

See tests/AUTH_TEST_NOTES.md for why the original 1.2-era plain-JSON cookie
fixtures were modernized.

Run: pip install -e ".[dev]" && pytest tests/test_rest.py -q
"""
from __future__ import annotations

import os
from typing import Any, Optional

from fastapi.testclient import TestClient

from api.auth_session import Session, serialize_session
from api.discord_client import FakeDiscordClient
from api.main import create_app, get_repo, get_state_store
from api.security import SESSION_COOKIE

# Signing secret for the test session cookies. The app verifies the cookie with
# ``os.environ["SESSION_SECRET"]`` (api.security.parse_session_cookie), so the
# same value must be both serialized into the cookie and present in the env.
SECRET = "test-secret-please-change"  # noqa: S105 - test-only, not from prod

# A valid Snapshot per engine/schema.py (axis.step; regime.sign is int; levels
# are lists of floats / null). Mirrors the 0.8 golden shape.
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
    "profile": [
        {"strike": 5000.0, "net_gex": 1.0, "net_dex": 2.0, "interpolated": False}
    ],
    "field": {"price_grid": [5000.0], "gamma": [1.0], "delta": [2.0]},
    "levels": {
        "call_walls": [5010.0, 5015.0, 5005.0],
        "put_walls": [4990.0, 4985.0, 4995.0],
        "gamma_flip": None,
        "largest_gex": 4980.0,
        "largest_dex": 5010.0,
    },
}

def _desk_cookie() -> str:
    return serialize_session(
        Session(
            discord_id="123", has_desk=True, is_member=True, access_token="desk-tok"
        ),
        SECRET,
    )


def _no_desk_cookie() -> str:
    return serialize_session(
        Session(
            discord_id="123", has_desk=False, is_member=True, access_token="nodesk-tok"
        ),
        SECRET,
    )


class FakeState:
    def __init__(self, payload: Optional[dict[str, Any]]) -> None:
        self._payload = payload

    async def get_now(self, instrument: str) -> Optional[dict[str, Any]]:
        return self._payload


class FakeRepo:
    def __init__(self, sessions=None, rng=None) -> None:
        self._sessions = sessions if sessions is not None else [
            {"session_date": "2026-06-10", "minute_count": 390}
        ]
        self._rng = rng if rng is not None else [SAMPLE]

    async def list_sessions(self, instrument: str):
        return self._sessions

    async def get_range(self, instrument, date, from_minute, to_minute):
        return self._rng


def make_client(
    state_payload: Optional[dict[str, Any]] = SAMPLE,
    repo: Optional[FakeRepo] = None,
) -> TestClient:
    os.environ["SESSION_SECRET"] = SECRET
    os.environ["DISCORD_GUILD_ID"] = "guild-1"
    os.environ["DISCORD_DESK_ROLE_ID"] = "role-desk"
    app = create_app()
    # Inject a fake Discord client so the daily re-check in /api/me & recheck is
    # network-free and deterministic. Roles per access token mirror the cookie
    # entitlement, so a forced re-check keeps DESK for the desk session.
    fake = FakeDiscordClient(user_id="123")
    fake.set_roles(("role-desk",), access_token="desk-tok")
    fake.set_roles(("role-other",), access_token="nodesk-tok")
    app.state.discord_client = fake
    app.dependency_overrides[get_state_store] = lambda: FakeState(state_payload)
    app.dependency_overrides[get_repo] = lambda: repo or FakeRepo()
    return TestClient(app)


def _desk(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, _desk_cookie())


def _no_desk(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, _no_desk_cookie())


# --------------------------------------------------------------------------- #
# health                                                                       #
# --------------------------------------------------------------------------- #
def test_health_ok() -> None:
    client = make_client()
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "feed_mode", "version"}


# --------------------------------------------------------------------------- #
# snapshot gating + 200 + 404 + alias + invalid instrument                     #
# --------------------------------------------------------------------------- #
def test_snapshot_401_without_session() -> None:
    client = make_client()
    res = client.get("/api/snapshot", params={"instrument": "ES"})
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_snapshot_403_for_non_desk() -> None:  # T-09
    client = make_client()
    _no_desk(client)
    res = client.get("/api/snapshot", params={"instrument": "ES"})
    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_snapshot_200_for_desk() -> None:
    client = make_client()
    _desk(client)
    res = client.get("/api/snapshot", params={"instrument": "ES"})
    assert res.status_code == 200
    assert res.json()["instrument"] == "ES"
    assert res.json()["schema_version"] == 1


def test_snapshot_latest_alias_200() -> None:
    client = make_client()
    _desk(client)
    res = client.get("/api/snapshot/latest", params={"instrument": "ES"})
    assert res.status_code == 200
    assert res.json()["instrument"] == "ES"


def test_snapshot_404_when_none() -> None:
    client = make_client(state_payload=None)
    _desk(client)
    res = client.get("/api/snapshot", params={"instrument": "NQ"})
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_snapshot_422_invalid_instrument() -> None:
    client = make_client()
    _desk(client)
    res = client.get("/api/snapshot", params={"instrument": "XX"})
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"


# --------------------------------------------------------------------------- #
# replay sessions + range                                                      #
# --------------------------------------------------------------------------- #
def test_replay_sessions_401_without_session() -> None:
    client = make_client()
    res = client.get("/api/replay/sessions", params={"instrument": "ES"})
    assert res.status_code == 401


def test_replay_sessions_403_for_non_desk() -> None:
    client = make_client()
    _no_desk(client)
    res = client.get("/api/replay/sessions", params={"instrument": "ES"})
    assert res.status_code == 403


def test_replay_sessions_200_for_desk() -> None:
    client = make_client()
    _desk(client)
    res = client.get("/api/replay/sessions", params={"instrument": "ES"})
    assert res.status_code == 200
    body = res.json()
    assert body == [{"session_date": "2026-06-10", "minute_count": 390}]


def test_replay_200_for_desk() -> None:
    client = make_client()
    _desk(client)
    res = client.get(
        "/api/replay",
        params={
            "instrument": "ES",
            "date": "2026-06-10",
            "from_minute": 0,
            "to_minute": 389,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "snapshots" in body
    assert len(body["snapshots"]) == 1
    assert body["snapshots"][0]["instrument"] == "ES"


def test_replay_403_for_non_desk() -> None:
    client = make_client()
    _no_desk(client)
    res = client.get(
        "/api/replay",
        params={
            "instrument": "ES",
            "date": "2026-06-10",
            "from_minute": 0,
            "to_minute": 389,
        },
    )
    assert res.status_code == 403


# --------------------------------------------------------------------------- #
# me + recheck                                                                 #
# --------------------------------------------------------------------------- #
def test_me_200_anon_without_session() -> None:
    # Release 1.6: /api/me is PUBLIC. Anonymous callers get 200 ANON, NOT 401.
    # Hard gating (401/403) lives on the data endpoints. (STITCHING_GUIDE §9.)
    client = make_client()
    res = client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["access_state"] == "ANON"
    assert body["discord_id"] is None


def test_me_200_with_session() -> None:
    client = make_client()
    _no_desk(client)  # any valid session, even without DESK, can see /api/me
    res = client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["discord_id"] == "123"
    assert body["has_desk"] is False


def test_me_recheck_401_without_session() -> None:
    client = make_client()
    res = client.post("/api/me/recheck")
    assert res.status_code == 401


def test_me_recheck_200_with_session() -> None:
    client = make_client()
    _desk(client)
    res = client.post("/api/me/recheck")
    assert res.status_code == 200
    assert res.json()["has_desk"] is True
