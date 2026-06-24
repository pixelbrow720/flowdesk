"""FlowDesk feed adapters (PRD #8 §8).

One interface (:class:`FeedAdapter`), two implementations
(:class:`HistoricalSimAdapter`, :class:`LiveAdapter`). Selection is driven
solely by ``FEED_MODE`` so the engine/DB/FE never change when the mode flips
(AC-A3).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from engine.feed.base import (
    INSTRUMENTS,
    ChainRow,
    FeedAdapter,
    OptionChainMinute,
    OptionType,
    ensure_utc_minute,
    to_engine_chain,
)

__all__ = [
    "INSTRUMENTS",
    "ChainRow",
    "FeedAdapter",
    "OptionChainMinute",
    "OptionType",
    "ensure_utc_minute",
    "to_engine_chain",
    "make_adapter",
]


def make_adapter(
    feed_mode: str,
    *,
    data_dir: Optional[str | Path] = None,
    api_key: Optional[str] = None,
    quote_schema: Optional[str] = None,
) -> FeedAdapter:
    """Construct the feed adapter selected by ``feed_mode`` (AC-A3).

    * ``"historical"`` -> :class:`HistoricalSimAdapter` reading ``data_dir``.
    * ``"live"``       -> :class:`LiveAdapter` stub.

    The historical quote schema is ``quote_schema`` when given, else the
    ``QUOTE_SCHEMA`` env var, else ``"mbp-1"`` (back-compatible default). Set it
    to ``"bbo-1m"`` to read the cheaper per-minute BBO export.

    Imports of the concrete adapters are deferred to keep this package's import
    graph acyclic.
    """
    mode = feed_mode.strip().lower()
    if mode == "historical":
        if data_dir is None:
            raise ValueError("historical feed requires data_dir (DATA_DIR)")
        from engine.feed.historical import HistoricalSimAdapter

        schema = quote_schema or os.environ.get("QUOTE_SCHEMA", "mbp-1")
        return HistoricalSimAdapter(data_dir, quote_schema=schema)
    if mode == "live":
        # Refuse-by-default rail (Phase 3): contacting the real Databento
        # account requires an explicit second key, LIVE_FEED_ARMED=1. See
        # docs/architecture/live-feed-threat-model.md (F1, F3).
        from engine.feed.live import LiveAdapter, LiveFeedNotArmed

        if not LiveAdapter._is_armed():
            raise LiveFeedNotArmed(
                "FEED_MODE=live requested but LIVE_FEED_ARMED is not set. "
                "Refusing to construct LiveAdapter without explicit arming "
                "(see docs/architecture/live-feed-threat-model.md)."
            )
        # Honor the operator's QUOTE_SCHEMA live too (mirrors the historical
        # branch above). Defaulting live to the high-volume mbp-1 tick stream
        # while the operator picked bbo-1m would silently blow past the message
        # budget they sized for on a rate-limited account.
        schema = quote_schema or os.environ.get("QUOTE_SCHEMA") or "mbp-1"
        return LiveAdapter(api_key=api_key, quote_schema=schema)
    raise ValueError(f"unknown FEED_MODE {feed_mode!r}; expected 'historical' or 'live'")
