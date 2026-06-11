"""Signed session cookie + DESK gating core (PRD #6 §4/§5, T-09).

This is the crypto + entitlement *core* of Phase 3. It is deliberately
FastAPI-free and network-free so it can be unit-tested in isolation:

* :class:`Session`        -- the entitlement cache stored in the cookie.
* :func:`serialize_session` / :func:`deserialize_session`
                          -- HMAC-SHA256 signed, expiring cookie value
                             (``SESSION_SECRET``). ``itsdangerous`` is not
                             available offline, so signing is implemented with
                             the stdlib (``hmac`` + ``hashlib`` + base64url).
* :func:`check_access`    -- the PRD #6 §5 gating algorithm (daily re-check,
                             revocation grace until end-of-day **ET**).
* cookie helpers          -- exact flags: HttpOnly + Secure + SameSite=Lax, 7d.

NAMING NOTE: the TASK calls this ``session.py``, but ``api/session.py`` is
ALREADY the PRD #9 worker session-state machine shipped in release 1.4. To avoid
clobbering it this module is named ``auth_session.py`` (see README divergence).
"""
from __future__ import annotations

import base64
import enum
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError

__all__ = [
    "ET",
    "SESSION_COOKIE",
    "OAUTH_STATE_COOKIE",
    "SESSION_MAX_AGE_S",
    "OAUTH_STATE_MAX_AGE_S",
    "RECHECK_INTERVAL_S",
    "Session",
    "Access",
    "AccessResult",
    "SignatureError",
    "serialize_session",
    "deserialize_session",
    "sign_value",
    "verify_value",
    "end_of_day_et",
    "check_access",
    "set_session_cookie",
    "clear_session_cookie",
    "set_state_cookie",
    "clear_state_cookie",
    "MemberLike",
]

#: Exchange wall-clock timezone for the grace "end of day" computation.
ET = ZoneInfo("America/New_York")

#: Cookie names.
SESSION_COOKIE = "flowdesk_session"
OAUTH_STATE_COOKIE = "flowdesk_oauth_state"

#: Lifetimes (seconds). Session = 7 days (PRD #6 §4). CSRF state = 10 minutes.
SESSION_MAX_AGE_S = 7 * 24 * 60 * 60
OAUTH_STATE_MAX_AGE_S = 10 * 60

#: Daily re-check threshold (PRD #6 §6): re-check if > 24h since last_checked.
RECHECK_INTERVAL_S = 24 * 60 * 60


class Session(BaseModel):
    """Authenticated user session / entitlement cache (PRD #6 §4).

    Field names are stable across phases (``require_session``/``require_desk``
    and ``/api/me`` depend on them). ``last_checked`` is the PRD ``last_check_ts``
    (ISO-8601 ...Z). ``access_token`` is stored so daily/manual re-checks can
    call Discord WITHOUT introducing a new env key (the locked 12-key contract
    has no bot token); it is never exposed by ``/api/me``.
    """

    discord_id: str
    has_desk: bool = False
    is_member: bool = True
    last_checked: Optional[str] = None
    grace_until: Optional[str] = None
    access_token: Optional[str] = None


class Access(str, enum.Enum):
    """PRD #6 §5 gating outcomes."""

    ALLOW = "ALLOW"
    ALLOW_GRACE = "ALLOW_GRACE"
    DENY_NOT_MEMBER = "DENY_NOT_MEMBER"
    DENY_NO_DESK = "DENY_NO_DESK"

    @property
    def allowed(self) -> bool:
        return self in (Access.ALLOW, Access.ALLOW_GRACE)


class AccessResult(BaseModel):
    """Result of :func:`check_access`: the (possibly refreshed) session + verdict."""

    session: Session
    decision: Access
    changed: bool = False  # True if the session/cookie should be re-issued


class MemberLike(Protocol):
    """Shape of a Discord guild member returned by the client interface."""

    roles: tuple[str, ...]


class SignatureError(Exception):
    """Raised on a tampered/expired/malformed signed value."""


# --------------------------------------------------------------------------- #
# Signing primitives (HMAC-SHA256 + base64url; constant-time verification).    #
# --------------------------------------------------------------------------- #
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _secret_bytes(secret: str) -> bytes:
    if not secret:
        raise SignatureError("SESSION_SECRET is empty")
    return secret.encode("utf-8")


def sign_value(payload: dict[str, Any], secret: str) -> str:
    """Return ``b64(payload).b64(hmac)`` for an arbitrary JSON-able payload."""
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    mac = hmac.new(_secret_bytes(secret), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64e(mac)}"


def verify_value(token: Optional[str], secret: str, *, now: Optional[datetime] = None) -> dict[str, Any]:
    """Verify a token from :func:`sign_value`; enforce ``exp`` if present.

    Raises :class:`SignatureError` on any failure (missing, malformed, bad MAC,
    expired). Comparison is constant-time.
    """
    if not token or "." not in token:
        raise SignatureError("missing or malformed token")
    body, _, sig = token.partition(".")
    expected = hmac.new(_secret_bytes(secret), body.encode("ascii"), hashlib.sha256).digest()
    try:
        given = _b64d(sig)
    except (ValueError, TypeError) as exc:
        raise SignatureError("bad signature encoding") from exc
    if not hmac.compare_digest(expected, given):
        raise SignatureError("signature mismatch")
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, TypeError) as exc:
        raise SignatureError("bad payload encoding") from exc
    if not isinstance(payload, dict):
        raise SignatureError("payload is not an object")
    exp = payload.get("exp")
    if exp is not None:
        now = now or datetime.now(timezone.utc)
        if float(exp) < now.timestamp():
            raise SignatureError("token expired")
    return payload


def serialize_session(
    session: Session, secret: str, *, now: Optional[datetime] = None, max_age_s: int = SESSION_MAX_AGE_S
) -> str:
    """Sign a :class:`Session` into a cookie value with a 7-day expiry."""
    now = now or datetime.now(timezone.utc)
    payload = session.model_dump()
    payload["exp"] = now.timestamp() + max_age_s
    return sign_value(payload, secret)


def deserialize_session(
    token: Optional[str], secret: str, *, now: Optional[datetime] = None
) -> Optional[Session]:
    """Verify + decode a session cookie. Returns ``None`` on any failure."""
    try:
        payload = verify_value(token, secret, now=now)
    except SignatureError:
        return None
    payload.pop("exp", None)
    try:
        return Session.model_validate(payload)
    except ValidationError:
        return None


# --------------------------------------------------------------------------- #
# Grace computation (end of day in ET) + gating algorithm (PRD #6 §5).         #
# --------------------------------------------------------------------------- #
def end_of_day_et(now: datetime) -> datetime:
    """Return the end of the current **ET** calendar day as an aware UTC datetime.

    "End of day ET" == 00:00 ET of the following day (exclusive). Grace is active
    while ``now < grace_until``, i.e. through the remainder of today in ET. The
    returned value is in UTC so it stores/compares unambiguously.
    """
    now_et = now.astimezone(ET)
    next_day = (now_et + timedelta(days=1)).date()
    midnight_next_et = datetime(
        next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=ET
    )
    return midnight_next_et.astimezone(timezone.utc)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_access(
    session: Session,
    *,
    now: Optional[datetime] = None,
    member: Any = ...,
    desk_role_id: str,
    recheck_interval_s: int = RECHECK_INTERVAL_S,
    force: bool = False,
) -> AccessResult:
    """Apply the PRD #6 §5 gating algorithm.

    Parameters
    ----------
    session : current cached session.
    now : aware UTC datetime (defaults to wall-clock UTC).
    member : the freshly-fetched guild member for this re-check, where:
        * a member object with ``.roles`` -> user is in the guild,
        * ``None`` -> confirmed NOT a member (Discord 404),
        * the sentinel default ``...`` -> NO re-check performed this call
          (either not due, or Discord was unavailable -> keep cache, PRD #6 §5).
    desk_role_id : the DESK role id (from ``DISCORD_DESK_ROLE_ID``).
    force : force a re-check regardless of the daily schedule (manual recheck).

    Returns
    -------
    AccessResult with the (possibly refreshed) session, the :class:`Access`
    verdict, and ``changed`` indicating whether the cookie should be re-issued.

    Grace semantics: grace starts only on a genuine **revocation** (the user
    HAD desk and the fresh check shows they no longer do). A user who never had
    DESK is denied (DENY_NO_DESK) -- this matches the PRD #6 §7 error table and
    avoids the literal §5 pseudocode granting grace to never-DESK users.
    """
    now = now or datetime.now(timezone.utc)
    changed = False
    last = _parse_iso(session.last_checked)
    due = force or last is None or (now - last).total_seconds() > recheck_interval_s

    if due and member is not ...:
        new_is_member = member is not None
        new_has_desk = new_is_member and (desk_role_id in getattr(member, "roles", ()))
        was_desk = session.has_desk
        updates: dict[str, Any] = {
            "is_member": new_is_member,
            "has_desk": new_has_desk,
            "last_checked": _iso_z(now),
        }
        if new_has_desk:
            updates["grace_until"] = None
        elif was_desk and session.grace_until is None:
            # genuine revocation -> grace until end of day ET
            updates["grace_until"] = _iso_z(end_of_day_et(now))
        # never-desk users keep grace_until = None (no grace).
        session = session.model_copy(update=updates)
        changed = True

    # ----- verdict (PRD #6 §5) -----
    if session.has_desk:
        return AccessResult(session=session, decision=Access.ALLOW, changed=changed)
    grace = _parse_iso(session.grace_until)
    if grace is not None and now < grace:
        return AccessResult(session=session, decision=Access.ALLOW_GRACE, changed=changed)
    if not session.is_member:
        return AccessResult(session=session, decision=Access.DENY_NOT_MEMBER, changed=changed)
    return AccessResult(session=session, decision=Access.DENY_NO_DESK, changed=changed)


# --------------------------------------------------------------------------- #
# Cookie helpers (exact flags). ``response`` is any Starlette/FastAPI Response. #
# --------------------------------------------------------------------------- #
def set_session_cookie(response: Any, value: str, *, secure: bool = True) -> None:
    """Set the signed session cookie: HttpOnly + Secure + SameSite=Lax, 7 days."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=value,
        max_age=SESSION_MAX_AGE_S,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Any) -> None:
    """Clear the session cookie (logout)."""
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def set_state_cookie(response: Any, value: str, *, secure: bool = True) -> None:
    """Set the short-lived signed CSRF state cookie (HttpOnly + Secure + Lax)."""
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=value,
        max_age=OAUTH_STATE_MAX_AGE_S,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_state_cookie(response: Any) -> None:
    response.delete_cookie(key=OAUTH_STATE_COOKIE, path="/")
