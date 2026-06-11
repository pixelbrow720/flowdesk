"""Discord OAuth2 HTTP client (PRD #6 §3).

All Discord network access is hidden behind the :class:`DiscordClient`
Protocol so routes/tests never touch the network directly:

* :class:`HttpxDiscordClient` — the real implementation (lazy ``import httpx``;
  runtime dependency promoted in release 1.5).
* :class:`FakeDiscordClient` — an in-memory double for tests; **no network**.

Error taxonomy (consumed by api/auth.py and api/main.py):

* :class:`DiscordAuthError` (4xx, e.g. bad/expired code or token) -> surface 401.
* :class:`DiscordUnavailable` (network failure / 5xx) -> keep cached entitlement
  (PRD #6 §5: never lock the user out just because Discord is down).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable
from urllib.parse import urlencode

__all__ = [
    "AUTHORIZE_ENDPOINT",
    "TOKEN_ENDPOINT",
    "API_BASE",
    "OAUTH_SCOPES",
    "DiscordUser",
    "GuildMember",
    "DiscordError",
    "DiscordAuthError",
    "DiscordUnavailable",
    "DiscordClient",
    "HttpxDiscordClient",
    "FakeDiscordClient",
    "client_from_env",
]

# Canonical Discord endpoints (PRD #6 §3).
AUTHORIZE_ENDPOINT = "https://discord.com/oauth2/authorize"
TOKEN_ENDPOINT = "https://discord.com/api/oauth2/token"
API_BASE = "https://discord.com/api"
# Exact scope string required by the PRD.
OAUTH_SCOPES = "identify guilds.members.read"


@dataclass(frozen=True)
class DiscordUser:
    """Subset of GET /users/@me we rely on."""

    id: str


@dataclass(frozen=True)
class GuildMember:
    """Subset of the guild member object we rely on."""

    roles: tuple[str, ...]
    user_id: Optional[str] = None


class DiscordError(Exception):
    """Base class for Discord client errors."""


class DiscordAuthError(DiscordError):
    """A 4xx from Discord (invalid/expired code or access token).

    The auth layer maps this to HTTP 401 (re-login required).
    """


class DiscordUnavailable(DiscordError):
    """A network failure or 5xx from Discord.

    The gating layer keeps the cached entitlement instead of locking the user
    out (PRD #6 §5).
    """


@runtime_checkable
class DiscordClient(Protocol):
    """Interface for all Discord OAuth2 interactions (mockable)."""

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        """Build the Discord authorize URL (no network)."""
        ...

    def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        """Exchange an authorization code for an OAuth access token."""
        ...

    def fetch_user(self, *, access_token: str) -> DiscordUser:
        """GET /users/@me -> the authenticated user."""
        ...

    def fetch_member(self, *, access_token: str, guild_id: str) -> Optional[GuildMember]:
        """GET the user's member object for ``guild_id``.

        Returns ``None`` when the user is not a member of the guild (HTTP 404).
        """
        ...


def _build_authorize_url(*, client_id: str, state: str, redirect_uri: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "scope": OAUTH_SCOPES,
            "state": state,
            "redirect_uri": redirect_uri,
            "prompt": "consent",
        }
    )
    return f"{AUTHORIZE_ENDPOINT}?{query}"


class HttpxDiscordClient:
    """Real Discord client backed by ``httpx`` (imported lazily)."""

    def __init__(
        self, client_id: str, client_secret: str, *, timeout_s: float = 10.0
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout_s = timeout_s

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        return _build_authorize_url(
            client_id=self._client_id, state=state, redirect_uri=redirect_uri
        )

    def _post(self, url: str, data: dict[str, str]):
        import httpx

        try:
            resp = httpx.post(url, data=data, timeout=self._timeout_s)
        except httpx.HTTPError as exc:  # network/timeout
            raise DiscordUnavailable(str(exc)) from exc
        return resp

    def _get(self, url: str, access_token: str):
        import httpx

        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = httpx.get(url, headers=headers, timeout=self._timeout_s)
        except httpx.HTTPError as exc:
            raise DiscordUnavailable(str(exc)) from exc
        return resp

    @staticmethod
    def _raise_for_status(resp) -> None:
        code = resp.status_code
        if code >= 500:
            raise DiscordUnavailable(f"discord {code}")
        if code >= 400:
            raise DiscordAuthError(f"discord {code}")

    def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        resp = self._post(
            TOKEN_ENDPOINT,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        self._raise_for_status(resp)
        token = resp.json().get("access_token")
        if not token:
            raise DiscordAuthError("no access_token in token response")
        return str(token)

    def fetch_user(self, *, access_token: str) -> DiscordUser:
        resp = self._get(f"{API_BASE}/users/@me", access_token)
        self._raise_for_status(resp)
        return DiscordUser(id=str(resp.json()["id"]))

    def fetch_member(
        self, *, access_token: str, guild_id: str
    ) -> Optional[GuildMember]:
        resp = self._get(
            f"{API_BASE}/users/@me/guilds/{guild_id}/member", access_token
        )
        if resp.status_code == 404:
            return None  # not a member of the guild
        self._raise_for_status(resp)
        body = resp.json()
        roles = tuple(str(r) for r in body.get("roles", []))
        user_id = None
        user = body.get("user")
        if isinstance(user, dict) and user.get("id") is not None:
            user_id = str(user["id"])
        return GuildMember(roles=roles, user_id=user_id)


@dataclass
class FakeDiscordClient:
    """In-memory Discord client for tests (NO network).

    ``exchange_code`` always returns ``token``; ``fetch_user`` returns
    ``DiscordUser(id=user_id)``; ``fetch_member`` looks up roles in ``members``
    keyed by access token. A stored value of ``None`` means "not a member"
    (HTTP 404 -> returns ``None``). Set ``raise_unavailable=True`` to simulate
    Discord being down. ``calls`` records the method call order for assertions.
    """

    user_id: str = "fake-user"
    token: str = "fake-token"
    client_id: str = "fake-client-id"
    members: dict[str, Optional[tuple[str, ...]]] = field(default_factory=dict)
    raise_unavailable: bool = False
    raise_auth_error: bool = False
    calls: list[str] = field(default_factory=list)

    def set_roles(
        self, roles: Optional[tuple[str, ...]], *, access_token: Optional[str] = None
    ) -> None:
        """Set the roles returned for ``access_token`` (defaults to ``token``).

        Pass ``roles=None`` to simulate the user not being a guild member.
        """
        self.members[access_token or self.token] = roles

    def _maybe_fail(self) -> None:
        if self.raise_unavailable:
            raise DiscordUnavailable("fake: discord down")
        if self.raise_auth_error:
            raise DiscordAuthError("fake: auth error")

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        self.calls.append("authorize_url")
        return _build_authorize_url(
            client_id=self.client_id, state=state, redirect_uri=redirect_uri
        )

    def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        self.calls.append("exchange_code")
        self._maybe_fail()
        return self.token

    def fetch_user(self, *, access_token: str) -> DiscordUser:
        self.calls.append("fetch_user")
        self._maybe_fail()
        return DiscordUser(id=self.user_id)

    def fetch_member(
        self, *, access_token: str, guild_id: str
    ) -> Optional[GuildMember]:
        self.calls.append("fetch_member")
        self._maybe_fail()
        roles = self.members.get(access_token, ())
        if roles is None:
            return None  # not a member
        return GuildMember(roles=tuple(roles), user_id=self.user_id)


def client_from_env() -> HttpxDiscordClient:
    """Build the real Discord client from env (secrets only from env)."""
    return HttpxDiscordClient(
        client_id=os.environ.get("DISCORD_CLIENT_ID", ""),
        client_secret=os.environ.get("DISCORD_CLIENT_SECRET", ""),
    )
