"""Snapshot assembler for FlowDesk (step 1.3).

Orchestrates the full per-(instrument, minute) compute pipeline and emits ONE
canonical :class:`engine.schema.Snapshot` (``schema_version`` 1):

    raw chain quotes
        -> IV solve            (engine.iv.implied_vol / is_iv_reliable)
        -> greeks              (engine.black76.delta / gamma)
        -> per-strike exposure (engine.exposure.build_profile / net_gamma)
        -> heatmap field       (engine.field.build_field)
        -> key levels          (engine.levels.compute_levels)
        -> regime + session stamping
        -> validated Snapshot  (engine.schema)

The builder is pure and deterministic: identical inputs always produce an
identical Snapshot. It owns **no calendar logic** — the caller supplies the
resolved ``session_state`` (PRD #9); the only time math here is converting the
UTC timestamp to the America/New_York RTH open to derive ``minute_index`` and
``session_date`` (PRD #8 §3).

Locked conventions (PRD #0)
===========================
* Multiplier ``M``: /ES = $50/pt, /NQ = $20/pt (PRD #0 §4).
* RTH open = 09:30 America/New_York; ``minute_index`` = 0 at the open.
* Forward ``F`` = futures price; ``rate`` = continuous annual ``r = ln(1+SOFR)``.
* Walls come from OPEN INTEREST (static); the gamma flip, largest GEX/DEX and
  the regime sign come from the VOL-based exposure profile.

Only the standard library + the sibling ``engine`` modules are imported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Mapping, Optional, Sequence, Union
from zoneinfo import ZoneInfo

from engine.black76 import delta as bs_delta
from engine.black76 import gamma as bs_gamma
from engine.exposure import ChainRow, build_profile, net_gamma
from engine.field import Axis as FieldAxis
from engine.field import build_field
from engine.iv import implied_vol, is_iv_reliable
from engine.levels import compute_levels
from engine.schema import (
    SCHEMA_VERSION,
    Snapshot,
    parse_snapshot,
)

if TYPE_CHECKING:  # pragma: no cover - typing only (no import-time cycle)
    from engine.hiro import HiroSnapshot

__all__ = [
    "MULTIPLIER",
    "RTH_OPEN_HOUR",
    "RTH_OPEN_MINUTE",
    "RTH_CLOSE_HOUR",
    "RTH_CLOSE_MINUTE",
    "SECONDS_PER_YEAR",
    "T_EXPIRY_FLOOR",
    "NY_TZ",
    "ChainQuote",
    "AxisInput",
    "build_snapshot",
    "minute_index_from_open",
    "session_date_for",
    "t_expiry_from_clock",
]

#: Instrument contract multiplier, USD per index point (PRD #0 §4).
MULTIPLIER = {"ES": 50.0, "NQ": 20.0}
#: RTH open (America/New_York). ``minute_index`` = 0 at this wall-clock time.
RTH_OPEN_HOUR = 9
RTH_OPEN_MINUTE = 30
#: RTH close (America/New_York) = 0DTE settlement reference (locked: 16:00 ET).
RTH_CLOSE_HOUR = 16
RTH_CLOSE_MINUTE = 0
#: Year length annualising the clock-based t_expiry. Matches the 365-day
#: convention of the locked ``DEFAULT_T_EXPIRY = 0.5/365`` and ``r = ln(1+SOFR)``.
SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0
#: Floor so t_expiry stays strictly positive (Black-76 is degenerate at T<=0).
T_EXPIRY_FLOOR = 1.0 / SECONDS_PER_YEAR
NY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ChainQuote:
    """One raw per-strike option-chain quote (engine input, pre-IV).

    ``call_vol`` / ``put_vol`` are cumulative volumes since the RTH open (drive
    every VOL-based metric). ``call_oi`` / ``put_oi`` are the day's open interest
    (drive the STATIC walls only). ``t_expiry`` is the year-fraction to the 0DTE
    expiry for this quote; when ``None`` the snapshot-level ``t_expiry`` is used.
    Optional bid/ask let the IV reliability gate detect crossed/thin quotes.
    A strike is treated as *thin* (greeks interpolated downstream) when either
    leg's quote is unreliable or its IV cannot be solved; ``thin=True`` forces
    it.
    """

    strike: float
    call_mid: Optional[float] = None
    put_mid: Optional[float] = None
    call_vol: float = 0.0
    put_vol: float = 0.0
    call_oi: float = 0.0
    put_oi: float = 0.0
    call_bid: Optional[float] = None
    call_ask: Optional[float] = None
    put_bid: Optional[float] = None
    put_ask: Optional[float] = None
    t_expiry: Optional[float] = None
    thin: bool = False


class AxisInput:
    """Structural alias: any object/dict exposing strike_min/strike_max/step."""


def _axis_triple(axis: object) -> tuple[float, float, float]:
    """Extract (strike_min, strike_max, step) from a dict or attr object."""
    if isinstance(axis, dict):
        smin, smax, step = axis["strike_min"], axis["strike_max"], axis["step"]
    else:
        smin, smax, step = axis.strike_min, axis.strike_max, axis.step
    return float(smin), float(smax), float(step)


def _to_utc(ts_utc: Union[str, datetime]) -> datetime:
    """Coerce an ISO-8601 string or datetime to an aware UTC datetime."""
    if isinstance(ts_utc, datetime):
        dt = ts_utc
    else:
        s = ts_utc.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_ts_z(dt_utc: datetime) -> str:
    """Render an aware UTC datetime as ISO-8601 seconds precision with 'Z'.

    Matches both the pydantic ``ts`` validator (endswith 'Z', parseable) and
    zod's ``z.string().datetime()`` (RFC-3339, 'Z' zone, seconds present).
    """
    return dt_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def session_date_for(ts_utc: Union[str, datetime]) -> str:
    """Trading session date (America/New_York) as ISO ``YYYY-MM-DD``."""
    return _to_utc(ts_utc).astimezone(NY_TZ).date().isoformat()


def minute_index_from_open(ts_utc: Union[str, datetime]) -> int:
    """Whole minutes since the 09:30 ET RTH open (0 at the open).

    Negative before the open, positive after. Uses floor division so a
    timestamp inside minute *m* maps to index *m* (e.g. 09:31:45 -> 1).
    """
    et = _to_utc(ts_utc).astimezone(NY_TZ)
    open_et = et.replace(
        hour=RTH_OPEN_HOUR, minute=RTH_OPEN_MINUTE, second=0, microsecond=0
    )
    return math.floor((et - open_et).total_seconds() / 60.0)


def t_expiry_from_clock(
    ts_utc: Union[str, datetime],
    *,
    settlement_hour: int = RTH_CLOSE_HOUR,
    settlement_minute: int = RTH_CLOSE_MINUTE,
) -> float:
    """Real-clock 0DTE year-fraction from ``ts`` to TODAY's settlement (ET).

    Divergence #3 option. Not the *engine* default (the pure engine keeps the
    calendar-free placeholder ``DEFAULT_T_EXPIRY = 0.5/365``), but the API worker
    DOES wire this as the runtime default per tick (see ``api.worker`` /
    ``DEFAULT_T_EXPIRY`` there) — so production snapshots use real wall-clock time.
    Where the locked ``DEFAULT_T_EXPIRY = 0.5/365`` is a near-constant placeholder,
    this returns the *actual* remaining time to the 16:00 ET (default) settlement,
    so charm/theta/gamma sharpen correctly through the afternoon for 0DTE.

    Returns the wall-clock seconds from ``ts`` to settlement, annualised by
    :data:`SECONDS_PER_YEAR` (365-day convention, matching the rest of the
    engine). The result is floored at :data:`T_EXPIRY_FLOOR` so it stays strictly
    positive at/after the bell (Black-76 is degenerate at ``T <= 0``); callers
    near/after settlement should treat the contract as expiring.

    Pure time math (UTC -> America/New_York); no calendar/holiday logic — the
    caller owns the session state. Flip the engine default to this only after
    Divergence #3 is approved (it shifts every snapshot number and the golden
    fixture, and can break T-01..T-10).
    """
    et = _to_utc(ts_utc).astimezone(NY_TZ)
    settle_et = et.replace(
        hour=settlement_hour, minute=settlement_minute, second=0, microsecond=0
    )
    seconds = (settle_et - et).total_seconds()
    frac = seconds / SECONDS_PER_YEAR
    return frac if frac > T_EXPIRY_FLOOR else T_EXPIRY_FLOOR


def _session_flags(
    state: str,
    stale: Optional[bool],
    expired: Optional[bool],
) -> tuple[bool, bool]:
    """Derive (stale, expired) from the resolved session_state (PRD #9).

    The engine does not own the calendar, so the flags follow deterministically
    from the caller-supplied state, with optional explicit overrides:
      * STALE            -> stale=True
      * CLOSED, HOLIDAY  -> expired=True (0DTE contracts no longer trading)
      * PREMARKET, LIVE  -> neither
    """
    default_stale = state == "STALE"
    default_expired = state in ("CLOSED", "HOLIDAY")
    return (
        default_stale if stale is None else bool(stale),
        default_expired if expired is None else bool(expired),
    )


def _solve_chain(
    chain: Sequence[ChainQuote],
    F: float,
    rate: float,
    snapshot_t: Optional[float],
) -> List[ChainRow]:
    """IV -> greeks for every strike, producing exposure-ready ChainRows.

    A leg with an unreliable quote or an unsolvable IV yields zero greeks and
    marks the strike thin; :func:`engine.exposure.build_profile` then
    interpolates the greeks from liquid neighbours. Observed volumes / OI are
    passed through untouched.
    """
    rows: List[ChainRow] = []
    for q in chain:
        T = q.t_expiry if q.t_expiry is not None else snapshot_t
        if T is None:
            raise ValueError(
                f"missing t_expiry for strike {q.strike!r}; supply it on the "
                f"quote or pass t_expiry= to build_snapshot"
            )
        K = float(q.strike)

        call_ok = is_iv_reliable(q.call_mid, bid=q.call_bid, ask=q.call_ask)
        put_ok = is_iv_reliable(q.put_mid, bid=q.put_bid, ask=q.put_ask)
        call_iv = (
            implied_vol("call", q.call_mid, F, K, T, rate) if call_ok else None
        )
        put_iv = (
            implied_vol("put", q.put_mid, F, K, T, rate) if put_ok else None
        )

        thin = q.thin or call_iv is None or put_iv is None
        if thin:
            cg = pg = cd = pd = 0.0
        else:
            cg = bs_gamma(F, K, T, rate, call_iv)
            pg = bs_gamma(F, K, T, rate, put_iv)
            cd = bs_delta("call", F, K, T, rate, call_iv)
            pd = bs_delta("put", F, K, T, rate, put_iv)

        rows.append(
            ChainRow(
                strike=K,
                call_gamma=cg,
                put_gamma=pg,
                call_delta=cd,
                put_delta=pd,
                call_vol=float(q.call_vol),
                put_vol=float(q.put_vol),
                call_oi=float(q.call_oi),
                put_oi=float(q.put_oi),
                thin=thin,
                # Carry IV + T so the field projection can re-evaluate Black-76
                # gamma/delta at each hypothetical spot (TRACE-style surface).
                call_iv=call_iv,
                put_iv=put_iv,
                t_expiry=T,
            )
        )
    return rows


def _regime(profile: Sequence) -> tuple[float, int, float]:
    """(net_gamma, sign, stability_pct) from the VOL exposure profile.

    ``sign`` is the exact sign of aggregate net gamma (PRD #0 §6). ``stability_pct``
    is a deterministic single-frame proxy in [0, 100]: the share of total
    |net_gex| that agrees with the dominant sign — i.e. how one-sided
    (“stable”) the gamma profile is. The full intraday-history stability lands
    in a later task; this proxy is monotone, bounded and history-free.
    """
    ng = net_gamma(profile)
    sign = 1 if ng > 0.0 else (-1 if ng < 0.0 else 0)
    total_abs = sum(abs(e.net_gex) for e in profile)
    stability = 0.0 if total_abs == 0.0 else min(100.0, 100.0 * abs(ng) / total_abs)
    return ng, sign, stability


def build_snapshot(
    instrument: str,
    ts_utc: Union[str, datetime],
    chain: Sequence[ChainQuote],
    forward: float,
    rate: float,
    session_state: str,
    axis: object,
    *,
    t_expiry: Optional[float] = None,
    smoothing_bw: float = 0.0,
    price_grid: Optional[Sequence[float]] = None,
    top_n: int = 3,
    stale: Optional[bool] = None,
    expired: Optional[bool] = None,
    ohlc: Optional[tuple[float, float, float, float]] = None,
    hiro: Optional["HiroSnapshot"] = None,
    net_flow: Optional["Mapping[tuple[float, bool], float]"] = None,
    net_flow_tiered: Optional["Mapping[tuple[float, bool], float]"] = None,
    synthetic_oi_w: float = 1.0,
    with_exposure_ext: bool = False,
    with_surface: bool = False,
) -> Snapshot:
    """Assemble ONE validated Snapshot for ``instrument`` at ``ts_utc``.

    Parameters
    ----------
    instrument : "ES" | "NQ".
    ts_utc : snapshot time, ISO-8601 UTC string (…Z) or aware/naive datetime
        (naive is assumed UTC).
    chain : per-strike :class:`ChainQuote` rows (any order).
    forward : futures price F (index points).
    rate : continuous annual rate r = ln(1 + SOFR).
    session_state : resolved PRD #9 state (engine does not compute the calendar).
    axis : shared strike axis (dict or object with strike_min/strike_max/step).
    t_expiry : snapshot-level year-fraction to expiry used for quotes that do
        not carry their own.
    smoothing_bw : optional Gaussian field smoothing bandwidth (index points).
    price_grid : optional explicit field price grid; defaults to the axis nodes.
    top_n : walls per side (default 3).
    stale / expired : optional explicit overrides of the PRD #9-derived flags.

    Returns
    -------
    A :class:`engine.schema.Snapshot`, validated by the pydantic contract. Its
    serialized form (``.to_json()``) carries exactly the keys of the TypeScript
    zod contract.
    """
    if instrument not in MULTIPLIER:
        raise ValueError(f"instrument must be 'ES' or 'NQ', got {instrument!r}")
    F = float(forward)
    M = MULTIPLIER[instrument]
    smin, smax, step = _axis_triple(axis)

    dt_utc = _to_utc(ts_utc)
    ts_str = _format_ts_z(dt_utc)
    session_date = session_date_for(dt_utc)
    minute_index = minute_index_from_open(dt_utc)
    stale_flag, expired_flag = _session_flags(session_state, stale, expired)

    # --- compute pipeline ------------------------------------------------- #
    rows = _solve_chain(chain, F, rate, t_expiry)
    profile = build_profile(rows, M, F)
    ng, sign, stability = _regime(profile)

    # Synthetic-OI #4 (EXPERIMENTAL, optional/additive): OI anchor updated by
    # native aggressor flow. Computed only when the caller supplies per-leg signed
    # flow (the worker aggregates it from the same tape HIRO uses); None otherwise,
    # mirroring the hiro/ohlc precedent. Does NOT touch the locked VOL-based GEX.
    syn_oi = None
    if net_flow is not None:
        from engine.synthetic_oi import build_synthetic_oi

        syn_oi = build_synthetic_oi(rows, net_flow, M, F, w=synthetic_oi_w)

    # Synthetic-OI #6 (EXPERIMENTAL): same hybrid model as #4 but on the SIZE-TIERED
    # flow map (retail odd-lots downweighted, institutional blocks up — thresholds
    # UNVALIDATED). Reuses the SyntheticOi shape; None unless the caller supplies the
    # tiered map. With tier weights all 1.0 it equals #4.
    syn_oi_tiered = None
    if net_flow_tiered is not None:
        from engine.synthetic_oi import build_synthetic_oi

        syn_oi_tiered = build_synthetic_oi(rows, net_flow_tiered, M, F, w=synthetic_oi_w)

    # Synthetic-OI #7 total-hedging (EXPERIMENTAL, optional/additive): gamma+charm+
    # vanna on the SAME synthetic position Q as #4. Computed only when the caller
    # supplies signed flow (the Q base needs it); None otherwise. Three separate
    # fields (units differ — never summed). Does NOT touch the locked VOL-based GEX.
    tot_hedge = None
    if net_flow is not None:
        from engine.total_hedging import build_total_hedging

        tot_hedge = build_total_hedging(rows, net_flow, M, F, rate, w=synthetic_oi_w)

    # Extended exposure VEX/CHEX (EXPERIMENTAL, optional/additive): vanna/charm
    # aggregated on the SAME VOL basis + locked dealer signs as GEX/DEX. Needs no
    # external tape (re-evaluates greeks from the carried per-leg IV + t_expiry),
    # so it is gated by an explicit flag rather than data availability. None unless
    # requested, mirroring the ohlc/hiro/synthetic_oi precedent. Does NOT touch the
    # locked VOL-based GEX/DEX.
    exp_ext = None
    if with_exposure_ext:
        from engine.exposure_ext import build_exposure_ext

        exp_ext = build_exposure_ext(rows, M, F, rate)

    # Vol surface (EXPERIMENTAL, optional/additive): raw-SVI slice + expected move
    # from the already-solved per-leg IVs. No external data; deterministic fit.
    # Gated by an explicit flag (like exposure_ext); None unless requested or when
    # fewer than 5 non-thin strikes exist. Does NOT touch the locked profile.
    surface = None
    if with_surface:
        from engine.surface import build_surface

        surf_t = next((r.t_expiry for r in rows if not r.thin and r.t_expiry), t_expiry)
        if surf_t is not None:
            surface = build_surface(rows, F, surf_t)

    field = build_field(
        rows, FieldAxis(smin, smax, step), F, M, rate, price_grid,
        smoothing_bw=smoothing_bw,
    )
    # Walls by gamma-$ (Divergence #2 -> option B): rank strikes by
    # gamma_side * OI_side. The solved ``rows`` carry both the IV-derived
    # per-leg gamma and the day's OI, and structurally satisfy levels.OIPoint.
    levels = compute_levels(profile, rows, F, top_n=top_n)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "instrument": instrument,
        "session_date": session_date,
        "ts": ts_str,
        "minute_index": int(minute_index),
        "state": session_state,
        "stale": stale_flag,
        "expired": expired_flag,
        "forward": F,
        "rate": float(rate),
        "axis": {"strike_min": smin, "strike_max": smax, "step": step},
        "regime": {"net_gamma": ng, "sign": sign, "stability_pct": stability},
        "profile": [
            {
                "strike": e.strike,
                "net_gex": e.net_gex,
                "net_dex": e.net_dex,
                "interpolated": e.interpolated,
            }
            for e in profile
        ],
        "field": field.to_dict(),
        "levels": levels,
        "ohlc": (
            {"o": ohlc[0], "h": ohlc[1], "l": ohlc[2], "c": ohlc[3]}
            if ohlc is not None
            else None
        ),
        "hiro": (
            {
                "total": hiro.total,
                "calls": hiro.calls,
                "puts": hiro.puts,
                "zerodte": hiro.zerodte,
                "retail": hiro.retail,
            }
            if hiro is not None
            else None
        ),
        "synthetic_oi": syn_oi.to_dict() if syn_oi is not None else None,
        "synthetic_oi_tiered": (
            syn_oi_tiered.to_dict() if syn_oi_tiered is not None else None
        ),
        "exposure_ext": exp_ext.to_dict() if exp_ext is not None else None,
        "total_hedging": tot_hedge.to_dict() if tot_hedge is not None else None,
        "surface": surface.to_dict() if surface is not None else None,
    }
    # parse_snapshot enforces the full pydantic contract (raises on drift).
    return parse_snapshot(payload)
