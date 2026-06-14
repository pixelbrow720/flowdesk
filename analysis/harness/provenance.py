"""Tenor provenance contract for the offline analysis / validation harness.

Core principle
==============
A number cannot be produced without (a) asserting the *tenor* it claims and
(b) stamping a deterministic *fingerprint* of the data it was computed on. The
harness computes 0DTE GEX/DEX-style descriptors; if the underlying option legs
are not actually 0DTE (expiry == session date) every downstream metric is
silently wrong. This module makes that assumption EXPLICIT and FAIL-CLOSED.

Why this exists
---------------
The real 0DTE pull on disk (``data/raw/zerodte/{trades,statistics,bbo-1m}``)
is clean (expiry == session for every confirmed day), but the loaders that map
``instrument_id -> expiry`` are duplicated across the analysis tree and a future
re-pull (e.g. an accidental quarterly definition file with expiry 9-16 days out)
would contaminate the chain with no loud failure. ``assert_0dte`` is the guard:
construct the per-session leg set, call it BEFORE any metric/snapshot, and a
non-0DTE set raises ``TenorContaminationError`` instead of producing a bogus
number.

What is hashed (fingerprint stability)
--------------------------------------
``DataProvenance.fingerprint`` is ``sha256`` over a canonical, deterministic
serialization of the leg metadata:

  1. Legs are sorted by ``instrument_id`` (stable, integer key).
  2. Each leg becomes the line ``"{instrument_id}|{expiration_ns}|{strike!r}|{instrument_class}"``
     where ``strike!r`` is Python's ``repr`` of the float (round-trip stable in
     CPython).
  3. Lines are joined with ``"\n"`` and UTF-8 encoded.

This is stable across a clean re-pull as long as the same legs (same ids,
expiries, strikes, classes) are present, and changes the moment any leg's
identity/expiry/strike/class changes — i.e. it detects a silently-swapped
definition file.

Time-zone correctness
---------------------
``expiration`` is an epoch-nanosecond UTC integer stamped at 16:00 America/
New_York. The session-date compare MUST be done in ET, not UTC, or a 16:00 ET
expiry lands on the next UTC day and false-rejects by one day. We convert via
``zoneinfo("America/New_York")``.

Scope / follow-up
-----------------
Only ``assert_0dte`` is implemented for now (the general ``assert_tenor``
contract can come later). Only the live ``run_validation.py`` chokepoint is
wired in this phase.

TODO (follow-up, NOT done here): route the other duplicated
``instrument_id -> expiry`` loaders through this guard so no metric path can
skip it. Known call sites:
  - ``analysis/harness/run_validation.py``  -> ``load_defs``        (WIRED)
  - ``analysis/lapis1.py``                  -> ``build_iid_map``    (TODO)
  - ``analysis/rerun_zerodte.py``           -> def loader           (TODO)
  - ``analysis/synthetic_oi_v2.py``         -> def loader           (TODO)
  - ``analysis/synthetic_oi_v3.py``         -> def loader           (TODO)
  - ``analysis/synthetic_oi_v4.py``         -> def loader           (TODO)
  - ``analysis/ddoi.py``                    -> reuses lapis1 loader (TODO)
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

#: 0DTE expiries are stamped at 16:00 in this zone; the session-date compare
#: is done here, never in UTC.
NY = ZoneInfo("America/New_York")

#: Wall-clock close used as the reference instant for "days to expiry".
RTH_CLOSE_HOUR = 16

#: Option classes accepted on a 0DTE chain. Anything else is contamination.
_OPTION_CLASSES = ("C", "P")


class TenorContaminationError(Exception):
    """Raised (fail-closed) when data does not match the declared tenor.

    Carries an actionable message naming the declared tenor, the session date,
    and what was actually observed.
    """


@dataclass(frozen=True)
class LegMeta:
    """Clean, databento-decoupled description of one option leg.

    Callers extract these fields from whatever definition source they use and
    pass a plain list, so this contract never depends on databento record types.
    """

    instrument_id: int
    expiration_ns: int  # epoch nanoseconds, UTC (stamped 16:00 ET)
    strike: float
    instrument_class: str  # "C" or "P"
    instrument: str  # underlying label, e.g. "ES" / "NQ"


@dataclass(frozen=True)
class DefLeg:
    """A single definition leg, keyed externally by ``instrument_id``.

    This is the value type of the *full* ``{instrument_id -> leg}`` definition
    map (ALL expiries, not bucketed by expiry). ``instrument_id`` is the map KEY,
    so it is deliberately absent here. Used by :func:`assert_session_iids_0dte`,
    which resolves a raw traded/settled id population against this map.
    """

    expiration_ns: int  # epoch nanoseconds, UTC (stamped 16:00 ET)
    strike: float
    instrument_class: str  # "C" or "P"
    instrument: str  # underlying label, e.g. "ES" / "NQ"


@dataclass(frozen=True)
class DataProvenance:
    """Stamped proof of the tenor + data identity behind a metric run."""

    source_label: str
    session_date: date
    expiry_set: tuple[date, ...]  # sorted unique expiries observed (ET)
    n_legs: int
    instruments: tuple[str, ...]  # sorted unique underlyings observed
    fingerprint: str  # sha256 hex; see module docstring for exact preimage
    realized_tenor_days: float  # max days-to-expiry at session 16:00 ET (0.0 = 0DTE)

    def summary(self) -> str:
        """One-line, human-readable provenance string."""
        exp = ",".join(d.isoformat() for d in self.expiry_set)
        return (
            f"{self.source_label} session={self.session_date.isoformat()} "
            f"expiry={{{exp}}} n_legs={self.n_legs} "
            f"fp={self.fingerprint[:12]}"
        )


def _et_datetime(expiration_ns: int) -> datetime:
    """Epoch-ns (UTC) -> aware datetime in America/New_York."""
    return datetime.fromtimestamp(expiration_ns / 1e9, tz=timezone.utc).astimezone(NY)


def _fingerprint(legs: Sequence[LegMeta]) -> str:
    """sha256 over the canonical leg serialization (see module docstring)."""
    ordered = sorted(legs, key=lambda leg: leg.instrument_id)
    lines = [
        f"{leg.instrument_id}|{leg.expiration_ns}|{leg.strike!r}|{leg.instrument_class}"
        for leg in ordered
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def assert_0dte(
    legs: Sequence[LegMeta],
    session_date: date,
    *,
    source_label: str,
) -> DataProvenance:
    """Assert that ``legs`` are a clean 0DTE set (expiry == session date, ET).

    FAIL-CLOSED. Raises :class:`TenorContaminationError` if:
      * ``legs`` is empty (never silently pass an empty set);
      * any leg's ``instrument_class`` is not "C"/"P";
      * any leg's ET expiry date != ``session_date``;
      * more than one unique ET expiry date is present;
      * any leg's days-to-expiry (relative to session 16:00 ET) is >= 1.

    On success returns a fully-populated :class:`DataProvenance` with
    ``realized_tenor_days`` ~ 0.0.
    """
    declared = "0DTE: expiry==session"
    if not legs:
        raise TenorContaminationError(
            f"{declared}: refusing to compute on EMPTY leg set "
            f"(source={source_label!r}, session={session_date.isoformat()}). "
            f"An empty chain is not a valid 0DTE session — fix the loader/filter."
        )

    session_close = datetime(
        session_date.year, session_date.month, session_date.day,
        RTH_CLOSE_HOUR, 0, tzinfo=NY,
    )

    expiry_dates: set[date] = set()
    instruments: set[str] = set()
    realized_tenor_days = 0.0

    for leg in legs:
        ic = leg.instrument_class
        if ic not in _OPTION_CLASSES:
            raise TenorContaminationError(
                f"{declared}: unexpected instrument_class {ic!r} on "
                f"{leg.instrument!r} (iid={leg.instrument_id}); a 0DTE option "
                f"chain may only contain {_OPTION_CLASSES}. source={source_label!r}"
            )
        exp_dt = _et_datetime(leg.expiration_ns)
        exp_date = exp_dt.date()
        expiry_dates.add(exp_date)
        instruments.add(leg.instrument)
        days = (exp_dt - session_close).total_seconds() / 86400.0
        if days > realized_tenor_days:
            realized_tenor_days = days

    sorted_expiries = tuple(sorted(expiry_dates))

    if len(sorted_expiries) > 1:
        found = ", ".join(d.isoformat() for d in sorted_expiries)
        raise TenorContaminationError(
            f"{declared}, session={session_date.isoformat()}: found MULTIPLE "
            f"distinct expiries [{found}] across {len(legs)} legs "
            f"(source={source_label!r}). A 0DTE set must have exactly one expiry "
            f"equal to the session date — definition data is contaminated."
        )

    only = sorted_expiries[0]
    if only != session_date:
        raise TenorContaminationError(
            f"{declared}, session={session_date.isoformat()}: observed expiry "
            f"{only.isoformat()} != session date (source={source_label!r}, "
            f"{len(legs)} legs). The chain is NOT 0DTE for this session."
        )

    if realized_tenor_days >= 1.0:
        raise TenorContaminationError(
            f"{declared}, session={session_date.isoformat()}: max days-to-expiry "
            f"{realized_tenor_days:.3f} >= 1.0 (source={source_label!r}). Expiry "
            f"date matched but the timestamp is too far from the 16:00 ET close — "
            f"likely a non-0DTE definition pull."
        )

    return DataProvenance(
        source_label=source_label,
        session_date=session_date,
        expiry_set=sorted_expiries,
        n_legs=len(legs),
        instruments=tuple(sorted(instruments)),
        fingerprint=_fingerprint(legs),
        realized_tenor_days=realized_tenor_days,
    )


def assert_session_iids_0dte(
    traded_iids: Iterable[int],
    def_map: Mapping[int, DefLeg],
    session_date: date,
    *,
    source_label: str,
) -> DataProvenance:
    """Assert a RAW traded/settled id population resolves to a clean 0DTE set.

    This is the NON-TAUTOLOGICAL wiring helper. Unlike calling
    :func:`assert_0dte` on a per-expiry-bucketed leg set (where the
    ``expiry == session`` check can never fire because the bucket key already
    IS the expiry), this function is fed the *raw* instrument ids actually
    observed in a session's trade/settlement streams and resolves each one
    against the FULL definition map (``def_map`` spans ALL expiries). A
    contaminated id whose true expiry is, say, 9 days out therefore resolves to
    a non-session ``DefLeg`` and trips :func:`assert_0dte`'s expiry check —
    which is impossible on the pre-bucketed path.

    FAIL-CLOSED. Raises :class:`TenorContaminationError` if:
      * any ``iid`` in ``traded_iids`` is NOT present in ``def_map`` — an
        unresolved traded/settled id is itself a lineage/contamination signal
        (we cannot prove its tenor, so we refuse);
      * the resolved legs fail :func:`assert_0dte` (empty set, non-option class,
        expiry != session, multiple expiries, or tenor >= 1 day).

    On success returns the :class:`DataProvenance` produced by
    :func:`assert_0dte` over the resolved legs.
    """
    declared = "0DTE(session-iids): expiry==session"
    leg_metas: list[LegMeta] = []
    for iid in traded_iids:
        leg = def_map.get(int(iid))
        if leg is None:
            raise TenorContaminationError(
                f"{declared}: traded/settled instrument_id {int(iid)} is NOT in "
                f"the definition map (source={source_label!r}, "
                f"session={session_date.isoformat()}). An unresolved traded id "
                f"means its tenor cannot be proven — refusing to compute "
                f"(definition lineage is incomplete or contaminated)."
            )
        leg_metas.append(
            LegMeta(
                instrument_id=int(iid),
                expiration_ns=leg.expiration_ns,
                strike=leg.strike,
                instrument_class=leg.instrument_class,
                instrument=leg.instrument,
            )
        )
    return assert_0dte(leg_metas, session_date, source_label=source_label)
