"""LiveAdapter — interface-compatible stub for the realtime Databento feed.

This is the ``FEED_MODE=live`` implementation. It is INTENTIONALLY a stub: the
authoring/CI sandbox has no network and no Databento subscription, so no live
stream is opened here. The class exists so that:

  * the live wiring is interface-compatible with :class:`HistoricalSimAdapter`
    (same :class:`~engine.feed.base.FeedAdapter` contract — AC-A3); and
  * the exact attach point for the realtime subscription is documented in one
    obvious place.

WHERE THE LIVE SUBSCRIPTION ATTACHES
------------------------------------
In production this adapter maintains a rolling, in-memory "current minute" book
per instrument, fed by Databento's realtime client, and emits a chain when each
minute closes. Sketch (do NOT enable in the sandbox):

    import databento as db

    client = db.Live(key=os.environ["DATABENTO_API_KEY"])
    client.subscribe(
        dataset="GLBX.MDP3",
        schema="definition",                 # then statistics / trades / mbp-1
        stype_in="parent",
        symbols=["ES.OPT", "ES.FUT", "NQ.OPT", "NQ.FUT"],
    )
    for record in client:
        self._apply(record)                  # update rolling per-minute book
        # on minute close -> assemble OptionChainMinute (same shape as historical)

The per-minute assembly (definition + OI + cumulative VOL + top-of-book mid) is
IDENTICAL to :class:`HistoricalSimAdapter`; only the data source differs. When
the live path is implemented it MUST return the same locked
:class:`~engine.feed.base.OptionChainMinute`, so the engine, datastore and
frontend stay byte-for-byte unchanged when ``FEED_MODE`` flips.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from engine.feed.base import FeedAdapter, OptionChainMinute, ensure_utc_minute

__all__ = ["LiveAdapter", "LiveFeedNotAvailable"]


class LiveFeedNotAvailable(RuntimeError):
    """Raised when the live feed is requested but not wired/available."""


_GUIDANCE = (
    "LiveAdapter is a stub: the realtime Databento subscription is not opened in "
    "this build (no network in the sandbox). Set FEED_MODE=historical to use the "
    "HistoricalSimAdapter, or implement LiveAdapter._connect() against databento.Live "
    "with a valid DATABENTO_API_KEY in your own deployment."
)


class LiveAdapter(FeedAdapter):
    """Realtime feed adapter (stub). Interface-compatible; raises on data calls."""

    mode = "live"

    def __init__(self, *, api_key: Optional[str] = None, dataset: str = "GLBX.MDP3") -> None:
        self.api_key = api_key
        self.dataset = dataset
        self._connected = False

    def _connect(self) -> None:
        """Attach the realtime subscription. Not implemented in the sandbox."""
        raise LiveFeedNotAvailable(_GUIDANCE)

    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        self._check_instrument(instrument)
        ensure_utc_minute(ts)  # validate shape even though we cannot serve data
        raise LiveFeedNotAvailable(_GUIDANCE)

    def get_forward(self, instrument: str, ts: datetime) -> float:
        self._check_instrument(instrument)
        ensure_utc_minute(ts)
        raise LiveFeedNotAvailable(_GUIDANCE)
