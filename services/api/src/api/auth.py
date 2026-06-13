"""Discord OAuth2 auth routes (PRD #6 §3/§4/§6, T-09).

Routes (canonical = PRD #6 §3 paths; the shorter TASK paths are registered as
aliases so both work):

  GET  /api/auth/discord/login      (alias GET  /api/auth/login)
      -> 307 redirect to the Discord authorize URL (scopes identify
         guilds.members.read) with a signed CSRF ``state`` cookie.
  GET  /api/auth/discord/callback   (alias GET  /api/auth/callback)
      -> verify state, exchange code -> token, fetch user + guild member,
         derive is_member / has_desk, mint a signed 7-day session cookie,
         redirect to the app.
  POST /api/auth/logout
      -> clear the session cookie.

All Discord I/O goes through the injected :class:`DiscordClient`
(``app.state.discord_client``) so tests use :class:`FakeDiscordClient`. Secrets
and the redirect target come ONLY from env.

This module imports FastAPI; the signing/entitlement logic it relies on lives in
:mod:`api.auth_session` (FastAPI-free) and the HTTP calls in
:mod:`api.discord_client`.
"""
from __future__ import annotations

import os
import secrets as _secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import RedirectResponse

from api.auth_session import (
    OAUTH_STATE_COOKIE,
    Session,
    clear_session_cookie,
    clear_state_cookie,
    serialize_session,
    set_session_cookie,
    set_state_cookie,
    sign_value,
    verify_value,
    SignatureError,
)
from api.discord_client import (
    DiscordAuthError,
    DiscordClient,
    DiscordUnavailable,
    client_from_env,
)
from api.errors import ApiError, Unauthenticated

__all__ = ["register_auth_routes", "get_discord_client", "redirect_uri_for", "cookies_secure"]


class BadRequest(ApiError):
    """400 for malformed OAuth callbacks (missing/invalid code or state)."""

    status_code = 400
    code = "BAD_REQUEST"


def _session_secret() -> str:
    return os.environ.get("SESSION_SECRET", "")


def _guild_id() -> str:
    return os.environ.get("DISCORD_GUILD_ID", "")


def _desk_role_id() -> str:
    # Locked contract uses DESK_ROLE_ID; fall back to the legacy DISCORD_DESK_ROLE_ID.
    return os.environ.get("DESK_ROLE_ID") or os.environ.get("DISCORD_DESK_ROLE_ID", "")


def cookies_secure() -> bool:
    """Whether cookies get the Secure flag.

    Defaults to True (production over HTTPS). Set ``COOKIE_INSECURE=1`` for local
    HTTP development only. Not a new locked env key -- purely an opt-out dev toggle.
    """
    return os.environ.get("COOKIE_INSECURE", "").strip().lower() not in ("1", "true", "yes")


def _post_login_redirect() -> str:
    """Where to send the browser after a successful login (the SPA).

    Uses the first configured CORS origin (the web app) when present, else "/".
    """
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins[0] if origins else "/"


def redirect_uri_for(request: Request) -> str:
    """Build the OAuth redirect_uri for the callback route.

    Prefers ``PUBLIC_BASE_URL`` when set (production domain -- TODO-FROM-OWNER);
    otherwise derives it from the incoming request base URL.
    """
    base = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/api/auth/discord/callback"
    return str(request.url_for("auth_discord_callback"))


def get_discord_client(request: Request) -> DiscordClient:
    """Return the injected Discord client (override via ``app.state``)."""
    client = getattr(request.app.state, "discord_client", None)
    if client is None:
        client = client_from_env()
        request.app.state.discord_client = client
    return client


def _now() -> datetime:
    return datetime.now(timezone.utc)


def register_auth_routes(app: FastAPI) -> None:
    """Register the Discord OAuth2 routes on ``app``."""

    # ----- login: redirect to Discord authorize with a signed CSRF state -----
    @app.get("/api/auth/discord/login", name="auth_discord_login")
    @app.get("/api/auth/login", include_in_schema=False)
    async def auth_login(request: Request) -> Response:
        client = get_discord_client(request)
        nonce = _secrets.token_urlsafe(24)
        redirect_uri = redirect_uri_for(request)
        # Sign the nonce (+ exp) so the callback can verify it came from us.
        state_token = sign_value(
            {"nonce": nonce, "exp": _now().timestamp() + 600}, _session_secret()
        )
        url = client.authorize_url(state=state_token, redirect_uri=redirect_uri)
        response = RedirectResponse(url, status_code=307)
        set_state_cookie(response, state_token, secure=cookies_secure())
        return response

    # ----- callback: exchange code, fetch member, mint session -----
    @app.get("/api/auth/discord/callback", name="auth_discord_callback")
    @app.get("/api/auth/callback", include_in_schema=False, name="auth_callback_alias")
    async def auth_callback(
        request: Request,
        code: Optional[str] = Query(default=None),
        state: Optional[str] = Query(default=None),
    ) -> Response:
        # CSRF: the state in the query must match our signed state cookie.
        cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
        if not state or not cookie_state or state != cookie_state:
            raise BadRequest("invalid OAuth state")
        try:
            verify_value(state, _session_secret(), now=_now())
        except SignatureError as exc:
            raise BadRequest("invalid OAuth state signature") from exc
        if not code:
            raise BadRequest("missing authorization code")

        client = get_discord_client(request)
        redirect_uri = redirect_uri_for(request)
        try:
            token = await client.exchange_code(code=code, redirect_uri=redirect_uri)
            user = await client.fetch_user(access_token=token)
            member = await client.fetch_member(access_token=token, guild_id=_guild_id())
        except DiscordAuthError as exc:
            raise Unauthenticated("Discord authentication failed") from exc
        except DiscordUnavailable as exc:
            # Discord down during login: cannot establish entitlement.
            raise ApiError("Discord temporarily unavailable") from exc

        is_member = member is not None
        has_desk = is_member and (_desk_role_id() in (member.roles if member else ()))
        session = Session(
            discord_id=user.id,
            is_member=is_member,
            has_desk=has_desk,
            last_checked=_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            grace_until=None,
            access_token=token,
        )
        cookie = serialize_session(session, _session_secret(), now=_now())
        response = RedirectResponse(_post_login_redirect(), status_code=307)
        set_session_cookie(response, cookie, secure=cookies_secure())
        clear_state_cookie(response)
        return response

    # ----- logout: clear the session cookie -----
    @app.post("/api/auth/logout", name="auth_logout")
    async def auth_logout() -> Response:
        response = Response(status_code=204)
        clear_session_cookie(response)
        return response
