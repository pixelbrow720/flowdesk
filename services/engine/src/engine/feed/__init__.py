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
        from engine.feed.live import LiveAdapter

        return LiveAdapter(api_key=api_key)
    raise ValueError(f"unknown FEED_MODE {feed_mode!r}; expected 'historical' or 'live'")
