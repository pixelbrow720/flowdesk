"""FlowDesk — centralized env accessors for auth/session config.

These three helpers were previously copy-pasted across :mod:`api.main`,
:mod:`api.auth`, and :mod:`api.ws`. They are consolidated here so there is a
single source of truth. Behavior is intentionally unchanged:

* secrets/config are read from ``os.environ`` at CALL TIME (not import time) so
  tests and process env stay flexible;
* :func:`desk_role_id` keeps the locked-contract ``DESK_ROLE_ID`` key with a
  fallback to the legacy ``DISCORD_DESK_ROLE_ID``.

This module deliberately imports nothing from the FastAPI layer, so it can be
imported from anywhere without risking an import cycle.
"""
from __future__ import annotations

import os

__all__ = ["session_secret", "guild_id", "desk_role_id"]


def session_secret() -> str:
    """Read the signing secret from env (secrets only from env)."""
    return os.environ.get("SESSION_SECRET", "")


def guild_id() -> str:
    """Read the Discord guild id from env."""
    return os.environ.get("DISCORD_GUILD_ID", "")


def desk_role_id() -> str:
    """Read the DESK role id from env.

    Locked contract uses ``DESK_ROLE_ID``; fall back to the legacy
    ``DISCORD_DESK_ROLE_ID`` when the primary key is unset/empty.
    """
    return os.environ.get("DESK_ROLE_ID") or os.environ.get("DISCORD_DESK_ROLE_ID", "")
