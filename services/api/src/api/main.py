"""FlowDesk API entrypoint — REST contract (PRD #8 §6, PRD #10 §2) + WS (§7) +
Discord OAuth2 auth (PRD #6) + FE entitlement contract (release 1.6).

Endpoints:
  GET  /api/health                                 -> {status, feed_mode, version}
  GET  /api/snapshot?instrument=ES|NQ              -> latest Snapshot (Redis), 404 if none   [DESK]
  GET  /api/snapshot/latest?instrument=ES|NQ       -> alias of the above (PRD #8 §6 path)      [DESK]
  GET  /api/replay/sessions?instrument=ES|NQ       -> [{session_date, minute_count}] (Timescale) [DESK]
  GET  /api/replay?instrument&date&from_minute&to_minute -> {snapshots: Snapshot[]}             [DESK]
  GET  /api/me                                     -> PUBLIC entitlement projection (ANON ok)
  POST /api/me/recheck                             -> force a Discord re-check, 401 if anonymous
  GET  /api/auth/discord/login   (alias /api/auth/login)     -> redirect to Discord authorize
  GET  /api/auth/discord/callback(alias /api/auth/callback)  -> OAuth callback, mint session
  POST /api/auth/logout                            -> clear session
  WS   /ws?instrument=ES|NQ                        -> live snapshot stream (see api/ws.py)      [DESK]

Gating: data endpoints (snapshot, replay, /ws) depend on the DESK seam -> 401 if
unauthenticated, 403 if no DESK role and no active grace (PRD #6 §5, T-09).
``/api/me`` is intentionally PUBLIC and projects the session into an
ANON/NO_DESK/DESK ``access_state`` (see api/entitlement.py) so the FE can render
the denied/preview-blur experience without hitting a 401.

Backends are injected via dependencies (``get_state_store`` / ``get_repo``) so
tests can override them with fakes; real instances are created in the app
lifespan from REDIS_URL / TIMESCALE_DSN when present.
"""
from __future__ import annotations

import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from engine.schema import Instrument, Snapshot
from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import __version__
from api.auth import get_discord_client, register_auth_routes
from api.auth_session import Session, check_access, serialize_session, set_session_cookie
from api.discord_client import DiscordAuthError, DiscordUnavailable
from api.entitlement import build_me_response
from api.errors import ApiError, NotFound, ServiceUnavailable, TooManyRequests
from api.models import HealthResponse, MeResponse, ReplayResponse, ReplaySession
from api.security import (
    SESSION_COOKIE,
    parse_session_cookie,
    require_desk,
    require_session,
)
from api.ws import register_ws_routes

# --------------------------------------------------------------------------- #
# Settings helpers (read env at call time so tests/process env stay flexible). #
# --------------------------------------------------------------------------- #
_CORS_ORIGIN_RE = re.compile(r"^(https://[^/\s]+|http://localhost(:\d+)?)$")


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _validate_cors_config(origins: list[str], *, allow_credentials: bool) -> None:
    """Fail-fast CORS validation called at app build (PRD #8 hardening).

    Rules (Phase 1 Item 1, beta-readiness):
      1. ``CORS_ORIGINS`` containing the literal ``"*"`` while
         ``allow_credentials=True`` is silently rejected by browsers but the
         server has been booting clean — raise loudly so misconfig is caught
         in CI/staging, not in production where it manifests as "auth broken".
      2. Empty ``CORS_ORIGINS`` is allowed (some deployments are same-origin)
         but emits a WARN log so the operator notices the implicit lockdown.
      3. Every origin must match ``https://...`` or ``http://localhost[:port]``.
         Plain ``http://`` for non-localhost hosts is refused (cookies + creds
         over plaintext is a beta-disqualifier).
    """
    log = logging.getLogger("api.cors")
    if not origins:
        log.warning(
            "CORS_ORIGINS is empty; cross-origin requests will be blocked entirely. "
            "Set CORS_ORIGINS to a comma-separated allowlist "
            "(e.g. 'https://app.flowdesk.example,http://localhost:3000') "
            "or this WILL look like 'auth broken' in prod."
        )
        return
    if allow_credentials and any(o == "*" for o in origins):
        raise RuntimeError(
            "CORS_ORIGINS contains '*' while allow_credentials=True. "
            "Browsers reject this combo silently; refusing to boot. "
            "Use an explicit origin allowlist."
        )
    bad = [o for o in origins if not _CORS_ORIGIN_RE.match(o)]
    if bad:
        raise RuntimeError(
            "CORS_ORIGINS contains origins that are not https:// or "
            f"http://localhost[:port]: {bad!r}. Refusing to boot."
        )


def _feed_mode() -> str:
    return os.environ.get("FEED_MODE", "historical")


def _session_secret() -> str:
    return os.environ.get("SESSION_SECRET", "")


def _guild_id() -> str:
    return os.environ.get("DISCORD_GUILD_ID", "")


def _desk_role_id() -> str:
    # Locked contract uses DESK_ROLE_ID; fall back to the legacy DISCORD_DESK_ROLE_ID.
    return os.environ.get("DESK_ROLE_ID") or os.environ.get("DISCORD_DESK_ROLE_ID", "")


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Dependencies.                                                                #
# --------------------------------------------------------------------------- #
def current_session(request: Request) -> Session | None:
    """Read + verify the signed session cookie."""
    return parse_session_cookie(request.cookies.get(SESSION_COOKIE))


def require_session_dep(request: Request) -> Session:
    """401 if there is no session."""
    return require_session(current_session(request))


async def require_desk_dep(request: Request, response: Response) -> Session:
    """401 if unauthenticated, 403 if no DESK role and no active grace.

    Enforces entitlement freshness on the DATA PLANE: runs the daily Discord
    re-check (at most once per interval per session, via ``_run_access_check``)
    before gating, so a revoked role is caught on /api/snapshot, /api/replay*,
    etc. — not only on /api/me. A refreshed cookie is merged onto the response.
    """
    session = current_session(request)
    if session is not None:
        session = await _run_access_check(request, response, session, force=False)
    return require_desk(session)


def get_state_store(request: Request) -> Any:
    """Redis-backed live state store (override in tests)."""
    store = getattr(request.app.state, "state_store", None)
    if store is None:
        raise ServiceUnavailable("state store not configured")
    return store


def get_repo(request: Request) -> Any:
    """Timescale-backed snapshot repository (override in tests)."""
    repo = getattr(request.app.state, "repo", None)
    if repo is None:
        raise ServiceUnavailable("snapshot repository not configured")
    return repo


async def _enforce_rate_limit(scope: str, request: Request) -> None:
    """Check the rate limit for ``scope`` against ``request.client.host``.

    Raises :class:`TooManyRequests` (HTTP 429 + ``Retry-After``) when the
    caller is over budget. No-op when no limiter is wired (dev / no-Redis):
    the limiter itself fails open, so this stays consistent.
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


async def _run_access_check(
    request: Request, response: Response, session: Session, *, force: bool
) -> Session:
    """Run the PRD #6 §5 access check (daily or forced) and refresh the cookie.

    Calls Discord (via the injected client) only when a re-check is due/forced.
    On Discord unavailability or an invalid token the cached entitlement is kept
    (never lock suddenly, PRD #6 §5). When the session changes, a fresh signed
    cookie is set on ``response``.
    """
    now = _now()
    last = session.last_checked
    due = force or last is None
    if not due and last is not None:
        try:
            from api.auth_session import _parse_iso

            parsed = _parse_iso(last)
            due = parsed is None or (now - parsed).total_seconds() > 24 * 60 * 60
        except Exception:
            due = True

    member: Any = ...  # sentinel: "no re-check performed"
    if due:
        client = get_discord_client(request)
        try:
            member = await client.fetch_member(
                access_token=session.access_token or "", guild_id=_guild_id()
            )
        except (DiscordUnavailable, DiscordAuthError):
            member = ...  # keep cache; banner "verification pending" on FE

    result = check_access(
        session, now=now, member=member, desk_role_id=_desk_role_id(), force=force
    )
    if result.changed:
        cookie = serialize_session(result.session, _session_secret(), now=now)
        set_session_cookie(response, cookie)
    return result.session


# --------------------------------------------------------------------------- #
# Lifespan: wire real backends from env when available (optional).            #
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_url = os.environ.get("REDIS_URL")
    dsn = os.environ.get("TIMESCALE_DSN")
    pool = None
    app.state.state_store = None
    app.state.repo = None
    app.state.rate_limiter = None
    if getattr(app.state, "discord_client", None) is None:
        from api.discord_client import client_from_env

        app.state.discord_client = client_from_env()
    if redis_url:
        from api.rate_limit import RateLimiter
        from api.state import create_client, create_state_store

        app.state.state_store = create_state_store(redis_url)
        # Separate redis-py client for rate-limit counters so flushing the
        # limiter never collides with snapshot pub/sub state.
        app.state.rate_limiter = RateLimiter(create_client(redis_url))
    else:
        # Dev / no-Redis mode: limiter still installed but disabled (fail-open).
        from api.rate_limit import RateLimiter

        app.state.rate_limiter = RateLimiter(client=None)
    if dsn:
        from db.repo import SnapshotRepository, apply_migrations, create_pool

        pool = await create_pool(dsn)
        # Apply pending migrations on boot (idempotent; tracked in schema_migrations).
        try:
            async with pool.acquire() as conn:
                await apply_migrations(conn)
        except Exception:  # log-and-continue; don't crash boot on migrate
            import logging

            logging.getLogger("api.main").exception("apply_migrations failed on boot")
        app.state.repo = SnapshotRepository(pool)
    try:
        yield
    finally:
        if pool is not None:
            await pool.close()


# --------------------------------------------------------------------------- #
# App factory.                                                                 #
# --------------------------------------------------------------------------- #
def create_app() -> FastAPI:
    app = FastAPI(title="FlowDesk API", version=__version__, lifespan=lifespan)

    _origins = _cors_origins()
    _validate_cors_config(_origins, allow_credentials=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def _api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        headers: dict[str, str] | None = None
        if isinstance(exc, TooManyRequests):
            # RFC 9110 §10.2.3 — clients (and well-behaved bots) honour this.
            headers = {"Retry-After": str(exc.retry_after)}
        return JSONResponse(
            status_code=exc.status_code, content=exc.to_payload(), headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "invalid request parameters", "code": "VALIDATION"},
        )

    @app.exception_handler(Exception)
    async def _catch_all_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Last-resort guard: never leak a stack trace; emit the structured shape.
        return JSONResponse(
            status_code=500,
            content={"error": "internal server error", "code": "INTERNAL"},
        )

    # ----- health -----
    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", feed_mode=_feed_mode(), version=__version__)

    # ----- snapshot (DESK-gated). /api/snapshot is the TASK path; -----
    # ----- /api/snapshot/latest is the PRD #8 §6 path (alias).    -----
    @app.get("/api/snapshot", response_model=Snapshot)
    @app.get("/api/snapshot/latest", response_model=Snapshot, include_in_schema=False)
    async def snapshot(
        instrument: Instrument = Query(...),
        _session: Session = Depends(require_desk_dep),
        store: Any = Depends(get_state_store),
    ) -> Snapshot:
        try:
            payload = await store.get_now(instrument)
        except ApiError:
            raise
        except Exception as exc:  # configured-but-down Redis -> 503, not raw 500
            raise ServiceUnavailable("state store unavailable") from exc
        if payload is None:
            raise NotFound(f"no snapshot available for {instrument}")
        return Snapshot.model_validate(payload)

    # ----- replay sessions (DESK-gated) -----
    @app.get("/api/replay/sessions", response_model=list[ReplaySession])
    async def replay_sessions(
        instrument: Instrument = Query(...),
        _session: Session = Depends(require_desk_dep),
        repo: Any = Depends(get_repo),
    ) -> list[ReplaySession]:
        rows = await repo.list_sessions(instrument)
        return [
            ReplaySession(
                session_date=str(row["session_date"]),
                minute_count=int(row["minute_count"]),
            )
            for row in rows
        ]

    # ----- replay range (DESK-gated) -----
    @app.get("/api/replay", response_model=ReplayResponse)
    async def replay(
        instrument: Instrument = Query(...),
        date: str = Query(...),
        from_minute: int = Query(..., ge=0),
        to_minute: int = Query(..., ge=0),
        _session: Session = Depends(require_desk_dep),
        repo: Any = Depends(get_repo),
    ) -> ReplayResponse:
        # Validate the date here so a malformed value is a 422, not a raw 500
        # from date.fromisoformat deep in the repo.
        from datetime import date as _date

        try:
            _date.fromisoformat(date)
        except ValueError as exc:
            raise ApiError(
                "date must be ISO YYYY-MM-DD", code="VALIDATION", status_code=422
            ) from exc
        if from_minute > to_minute:
            raise ApiError(
                "from_minute must be <= to_minute", code="VALIDATION", status_code=422
            )
        payloads = await repo.get_range(instrument, date, from_minute, to_minute)
        return ReplayResponse(
            snapshots=[Snapshot.model_validate(p) for p in payloads]
        )

    # ----- me (PUBLIC; ANON allowed). Daily re-check when a session exists. -----
    @app.get("/api/me", response_model=MeResponse)
    async def me(request: Request, response: Response) -> MeResponse:
        session = current_session(request)
        if session is not None:
            session = await _run_access_check(request, response, session, force=False)
        return build_me_response(session, now=_now())

    # ----- me/recheck (force an immediate Discord re-check; 401 if anonymous) -----
    @app.post("/api/me/recheck", response_model=MeResponse)
    async def me_recheck(request: Request, response: Response) -> MeResponse:
        # Rate-limit BEFORE auth: an anonymous flooder also gets capped per-IP
        # so they cannot DoS the Discord upstream by hammering 401s.
        await _enforce_rate_limit("recheck", request)
        session = require_session(current_session(request))
        session = await _run_access_check(request, response, session, force=True)
        return build_me_response(session, now=_now())

    # ----- Discord OAuth2 routes (login / callback / logout) -----
    register_auth_routes(app)

    # ----- WebSocket /ws (DESK-gated; see api/ws.py for the protocol) -----
    register_ws_routes(app)

    return app


app = create_app()
