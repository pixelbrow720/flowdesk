"""API response models.

The live/replay payload model is the canonical :class:`Snapshot` contract,
re-exported from the engine mirror (``engine/schema.py`` == the Python twin of
``packages/contracts``). We do NOT redefine it here: routes return the exact
contract so responses validate against ``schema_version = 1``.

The small wrapper models below (health / me / replay envelope) are API-only
shapes from PRD #8 §6 / PRD #10 §2 / the FE auth contract (release 1.6).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

# Canonical contract (single source of truth for the snapshot shape).
from engine.schema import Snapshot

__all__ = [
    "Snapshot",
    "HealthResponse",
    "AccessState",
    "Cta",
    "MeResponse",
    "ReplaySession",
    "ReplayResponse",
]

# FE entitlement enum (release 1.6). Drives the denied/preview-blur experience.
AccessState = Literal["ANON", "NO_DESK", "DESK"]


class HealthResponse(BaseModel):
    """GET /api/health (TASK shape). PRD #8 §6 adds engine_heartbeat_age_s later."""

    status: str
    feed_mode: str
    version: str


class Cta(BaseModel):
    """Call-to-action block for the gated FE experience (PRD #6, release 1.6).

    * ``join_url``         -- where a non-member goes to join the Discord guild.
    * ``buy_url``          -- where to purchase DESK access (locked: flowjob.id).
    * ``recheck_supported``-- whether the FE may offer the "cek ulang" button
      (POST /api/me/recheck). Always ``true`` for this backend.
    """

    join_url: str
    buy_url: str
    recheck_supported: bool = True


class MeResponse(BaseModel):
    """GET /api/me & POST /api/me/recheck (PRD #6 §7 / FE contract 1.6).

    ``/api/me`` is PUBLIC: anonymous callers get ``access_state = "ANON"`` (HTTP
    200), NOT a 401. Hard gating (401/403) lives on the data endpoints. The FE
    renders entirely from this shape:

    * ``access_state`` -- ANON | NO_DESK | DESK (see api/entitlement.py).
    * ``discord_id``   -- ``None`` when anonymous.
    * ``is_member``    -- still a guild member (distinguishes not-member copy).
    * ``grace_until``  -- ISO-8601 ...Z end of revocation grace (EOD ET) or None.
    * ``cta``          -- join/buy links + recheck capability.

    The OAuth access token is intentionally NOT exposed.
    """

    access_state: AccessState
    discord_id: Optional[str] = None
    has_desk: bool = False
    is_member: bool = False
    last_checked: Optional[str] = None
    grace_until: Optional[str] = None
    cta: Cta


class ReplaySession(BaseModel):
    """One available replay date. PRD #10 §2."""

    session_date: str
    minute_count: int


class ReplayResponse(BaseModel):
    """GET /api/replay envelope: ordered snapshots for playback. PRD #10 §2."""

    snapshots: list[Snapshot]
