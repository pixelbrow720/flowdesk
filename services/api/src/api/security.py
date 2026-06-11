"""DESK access seam (PRD #6 §5, acceptance T-09).

Pure module — no FastAPI import — so the gating logic stays unit-testable without
a web stack. ``main.py`` wraps these in FastAPI dependencies.

The signed-cookie crypto and the ``check_access`` re-check/grace algorithm live
in :mod:`api.auth_session`; this module is the thin gate the routes call:

* ``parse_session_cookie`` — verify + decode the signed cookie -> ``Session`` | None.
* ``require_session``      — 401 when there is no valid session.
* ``require_desk``         — 401 no session, 403 no DESK (respecting active grace).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from api.auth_session import (
    SESSION_COOKIE,
    Session,
    _parse_iso,
    deserialize_session,
)
from api.errors import Forbidden, Unauthenticated

__all__ = [
    "SESSION_COOKIE",
    "Session",
    "parse_session_cookie",
    "has_active_grace",
    "require_session",
    "require_desk",
]


def _session_secret() -> str:
    """Read the signing secret from env (secrets only from env)."""
    return os.environ.get("SESSION_SECRET", "")


def parse_session_cookie(raw: Optional[str]) -> Optional[Session]:
    """Verify + decode the signed session cookie.

    Returns ``None`` for a missing, tampered, or expired cookie (treated as
    "not signed in").
    """
    if not raw:
        return None
    return deserialize_session(raw, _session_secret())


def has_active_grace(session: Session, *, now: Optional[datetime] = None) -> bool:
    """True when a revocation grace window is still open (PRD #6 §5)."""
    if not session.grace_until:
        return False
    now = now or datetime.now(timezone.utc)
    grace = _parse_iso(session.grace_until)
    if grace is None:
        return False
    return now < grace


def require_session(session: Optional[Session]) -> Session:
    """401 when there is no valid session."""
    if session is None:
        raise Unauthenticated("authentication required")
    return session


def require_desk(
    session: Optional[Session], *, now: Optional[datetime] = None
) -> Session:
    """Gate data endpoints on the DESK entitlement.

    * no session            -> 401 UNAUTHENTICATED
    * has DESK               -> allow
    * within revocation grace-> allow (PRD #6 §5)
    * otherwise              -> 403 FORBIDDEN
    """
    sess = require_session(session)
    if sess.has_desk:
        return sess
    if has_active_grace(sess, now=now):
        return sess
    raise Forbidden("DESK role required")
