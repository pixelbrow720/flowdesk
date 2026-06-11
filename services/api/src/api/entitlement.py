"""Entitlement projection for the frontend (PRD #6 §5/§7, FE contract 1.6).

Maps a (possibly absent) :class:`~api.auth_session.Session` to the public
``/api/me`` shape the FE uses to render the gated experience:

* ``access_state`` enum -- ``ANON`` | ``NO_DESK`` | ``DESK``
* ``cta`` block -- where to send the user to join / buy + whether re-check works

Pure module (no FastAPI) so the exact response shape is unit-testable without a
web stack. ``main.py`` calls :func:`build_me_response` after running the daily/
forced access re-check.

State mapping:

* no session                      -> ``ANON``   (show login CTA)
* session with DESK role          -> ``DESK``   (full app)
* session within revocation grace -> ``DESK``   (full app + banner; PRD #6 §5)
* any other session               -> ``NO_DESK`` (blurred preview + join/buy)

``NO_DESK`` also covers the "not a guild member" case; the FE distinguishes it
via the ``is_member`` flag for copy nuance, but the gate is the same.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from api.auth_session import Session
from api.models import Cta, MeResponse
from api.security import has_active_grace

__all__ = [
    "ACCESS_ANON",
    "ACCESS_NO_DESK",
    "ACCESS_DESK",
    "BUY_URL",
    "join_url",
    "build_cta",
    "access_state_for",
    "build_me_response",
]

ACCESS_ANON = "ANON"
ACCESS_NO_DESK = "NO_DESK"
ACCESS_DESK = "DESK"

# Locked by TASK 1.6: the DESK purchase page.
BUY_URL = "https://flowjob.id"


def join_url() -> str:
    """Discord invite / join link.

    Sourced from the optional, non-locked ``DISCORD_JOIN_URL`` env var so ops can
    point it at the real guild invite. Falls back to :data:`BUY_URL` until the
    owner provides the invite (see TODO-FROM-OWNER).
    """
    return os.environ.get("DISCORD_JOIN_URL", BUY_URL)


def build_cta() -> Cta:
    """Call-to-action block returned for every ``/api/me`` response."""
    return Cta(join_url=join_url(), buy_url=BUY_URL, recheck_supported=True)


def access_state_for(
    session: Optional[Session], *, now: Optional[datetime] = None
) -> str:
    """Project a session into the ANON/NO_DESK/DESK enum."""
    if session is None:
        return ACCESS_ANON
    if session.has_desk:
        return ACCESS_DESK
    if has_active_grace(session, now=now):
        return ACCESS_DESK
    return ACCESS_NO_DESK


def build_me_response(
    session: Optional[Session], *, now: Optional[datetime] = None
) -> MeResponse:
    """Build the public ``/api/me`` body for any session (including none).

    The OAuth access token carried inside the session is never exposed here.
    """
    state = access_state_for(session, now=now)
    if session is None:
        return MeResponse(
            access_state=state,
            discord_id=None,
            has_desk=False,
            is_member=False,
            last_checked=None,
            grace_until=None,
            cta=build_cta(),
        )
    return MeResponse(
        access_state=state,
        discord_id=session.discord_id,
        has_desk=session.has_desk,
        is_member=session.is_member,
        last_checked=session.last_checked,
        grace_until=session.grace_until,
        cta=build_cta(),
    )
