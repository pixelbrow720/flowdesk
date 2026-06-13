"""FlowDesk — canonical Snapshot data contract (schema_version 1), Python mirror.

This module mirrors ``packages/contracts/src/snapshot.ts`` EXACTLY: identical
field names, casing, and semantics. Units come from PRD #0 (Glossary & Global
Contract) and the canonical schema in PRD #8 §3. See
``packages/contracts/CONTRACT.md`` for the field-by-field map.

Any breaking change MUST bump :data:`SCHEMA_VERSION` here and the TypeScript
mirror in lockstep.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

#: Canonical schema version. Bump on ANY breaking change.
SCHEMA_VERSION = 1

#: Tradable instrument. /ES (M=$50/pt, step 5) or /NQ (M=$20/pt, step 10). PRD #0 §4.
Instrument = Literal["ES", "NQ"]
#: Session state machine value. PRD #9, PRD #8 §3.
SessionState = Literal["PREMARKET", "LIVE", "STALE", "CLOSED", "HOLIDAY"]
#: Sign of net gamma. -1 negative / 0 flat / +1 positive. PRD #0 §6.
RegimeSign = Literal[-1, 0, 1]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Axis(BaseModel):
    """Strike axis bounds shared by the profile and the heatmap field."""

    model_config = ConfigDict(extra="forbid")

    strike_min: float
    """Lowest strike on the shared axis, in index points. PRD #8 §3."""
    strike_max: float
    """Highest strike on the shared axis, in index points. PRD #8 §3."""
    step: float = Field(gt=0)
    """Strike increment in index points (/ES = 5, /NQ = 10). PRD #0 §4."""


class Regime(BaseModel):
    """Market regime summary (sign of net gamma + stability %). PRD #4."""

    model_config = ConfigDict(extra="forbid")

    net_gamma: float
    """Aggregate dealer net gamma exposure, USD per 1% move. PRD #0 §5–§6."""
    sign: RegimeSign
    """Sign of ``net_gamma``: -1 | 0 | 1. PRD #0 §6."""
    stability_pct: float = Field(ge=0, le=100)
    """Regime stability, percent in [0, 100]. PRD #0 §2."""


class ProfileRow(BaseModel):
    """One strike row of the Net GEX/DEX profile. PRD #8 §3."""

    model_config = ConfigDict(extra="forbid")

    strike: float
    """Strike, in index points."""
    net_gex: float
    """Net dealer Gamma Exposure at this strike, USD per 1% move. PRD #0 §5."""
    net_dex: float
    """Net dealer Delta Exposure at this strike, USD notional. PRD #0 §2."""
    interpolated: bool
    """True if this strike's values were interpolated (synthetic). PRD #8 §3."""


class FieldGrid(BaseModel):
    """Heatmap field projection arrays (index-aligned, equal length). PRD #8 §3."""

    model_config = ConfigDict(extra="forbid")

    price_grid: list[float]
    """Price grid (index points) defining the field's price axis."""
    gamma: list[float]
    """Gamma field value at each grid point, USD per 1% move. PRD #0 §5."""
    delta: list[float]
    """Delta field value at each grid point, USD notional. PRD #8 §3."""

    @model_validator(mode="after")
    def _check_lengths(self) -> FieldGrid:
        """Enforce: price_grid defines the grid; gamma == delta == price_grid."""
        if len(self.gamma) != len(self.delta):
            raise ValueError(
                f"field.delta length ({len(self.delta)}) must equal "
                f"field.gamma length ({len(self.gamma)})"
            )
        if len(self.price_grid) != len(self.gamma):
            raise ValueError(
                f"field.gamma length ({len(self.gamma)}) must equal "
                f"field.price_grid length ({len(self.price_grid)})"
            )
        return self


class Levels(BaseModel):
    """Key levels overlay. PRD #0 §2, locked contract."""

    model_config = ConfigDict(extra="forbid")

    call_walls: list[float]
    """Call walls by OI, STATIC, ordered by rank (index 0 = rank 1). PRD #0 §2."""
    put_walls: list[float]
    """Put walls by OI, STATIC, ordered by rank (index 0 = rank 1). PRD #0 §2."""
    gamma_flip: float | None
    """Gamma flip strike (net-gamma zero-crossing) by VOL, or null. PRD #0 §2."""
    largest_gex: float | None
    """Strike of the largest GEX by VOL, or null. PRD #0 §2."""
    largest_dex: float | None
    """Strike of the largest DEX by VOL, or null. PRD #0 §2."""


class OHLC(BaseModel):
    """Underlying (futures forward) OHLC for this minute. PRD #4 candle view.

    Optional/additive: ``None`` for snapshots produced before OHLC capture was
    wired (no schema_version bump — absence is contract-valid)."""

    model_config = ConfigDict(extra="forbid")

    o: float
    """Open: first futures trade price in the minute, index points."""
    h: float
    """High: max futures trade price in the minute."""
    l: float  # noqa: E741 — locked OHLC field name (mirrors snapshot.ts)
    """Low: min futures trade price in the minute."""
    c: float
    """Close: last futures trade price in the minute (== forward)."""


class Hiro(BaseModel):
    """Cumulative dealer delta-notional hedging flow since the RTH open (HIRO).

    Optional/additive (Divergence #5 -> option A): ``None`` for snapshots
    produced before HIRO was wired, mirroring the ``ohlc`` precedent — absence is
    contract-valid and does NOT bump ``schema_version``. Units are USD
    delta-notional; positive = net dealer BUYING pressure (bullish), negative =
    selling pressure. These are the *current* cumulative values for this minute;
    the intraday HIRO line is reconstructed from the per-minute frame sequence
    (like the forward price line), not embedded per frame. See ``engine.hiro``."""

    model_config = ConfigDict(extra="forbid")

    total: float
    """Cumulative HIRO (all legs), USD delta-notional since RTH open."""
    calls: float
    """Cumulative HIRO from call trades only, USD delta-notional."""
    puts: float
    """Cumulative HIRO from put trades only, USD delta-notional."""
    zerodte: float
    """Cumulative HIRO from 0DTE trades (T < 1/365), USD delta-notional."""
    retail: float
    """Cumulative HIRO from the (heuristic) retail proxy, USD delta-notional."""


class SyntheticOi(BaseModel):
    """Synthetic-OI #4 positioning lens (EXPERIMENTAL — NOT price-validated).

    Optional/additive (mirrors ``hiro``/``ohlc``): ``None`` when not captured, no
    ``schema_version`` bump. Dealer position = carried-in open interest (static
    long-call/short-put sign) UPDATED by native CME aggressor-signed flow, weighted
    by ``w``. ``gex`` is the synthetic GEX at ``w``; ``gex_static`` is the ``w=0``
    pure-OI baseline (SpotGamma-classic). This lives ALONGSIDE the locked VOL-based
    product GEX and does NOT replace it. Validated only structurally on a 4-day
    sample — consumers MUST treat this as experimental, not authoritative. See
    ``engine.synthetic_oi`` and docs/research/empirical/synthetic-oi-0dte.md."""

    model_config = ConfigDict(extra="forbid")

    gex: float
    """Net synthetic-OI GEX at weight ``w``, USD per 1% move. EXPERIMENTAL."""
    sign: RegimeSign
    """Sign of ``gex``: -1 | 0 | 1."""
    gex_static: float
    """``w=0`` pure-OI GEX baseline (SpotGamma-classic), USD per 1% move."""
    w: float = Field(ge=0, le=1)
    """Open/close flow weight in [0, 1] used for ``gex``."""


class ExposureExt(BaseModel):
    """Extended dealer exposure — VEX (vanna) + CHEX (charm) (EXPERIMENTAL).

    Optional/additive (mirrors ``hiro``/``synthetic_oi``): ``None`` when not
    captured, no ``schema_version`` bump. Same VOL basis + locked dealer signs as
    the product GEX/DEX; lives ALONGSIDE them and does NOT replace them. The
    higher-order greeks are FD-validated, but the aggregate has never been checked
    against price — consumers MUST treat this as experimental, not authoritative.
    NOTE the units differ from GEX: ``net_vex`` is per **1% IV** (a vol-point
    scale), NOT per 1% price move; ``net_chex`` is per **calendar day**. See
    ``engine.exposure_ext`` and docs/research/empirical/track-f-ddoi-exposure-vol.md."""

    model_config = ConfigDict(extra="forbid")

    net_vex: float
    """Net vanna exposure, USD dealer dollar-delta per 1% IV move. EXPERIMENTAL."""
    vex_sign: RegimeSign
    """Sign of ``net_vex``: -1 | 0 | 1."""
    net_chex: float
    """Net charm exposure, USD dealer dollar-delta per calendar day. EXPERIMENTAL."""
    chex_sign: RegimeSign
    """Sign of ``net_chex``: -1 | 0 | 1."""


class TotalHedging(BaseModel):
    """Synthetic-OI #7 total-hedging map — gamma + charm + vanna on the Q base
    (EXPERIMENTAL — NOT price-validated).

    Optional/additive (mirrors ``synthetic_oi``/``exposure_ext``): ``None`` when not
    captured, no ``schema_version`` bump. Applies all three hedging greeks to the
    SAME synthetic dealer position ``Q`` as synthetic-OI #4 (OI anchor + flow,
    dealer sign baked in). THREE SEPARATE fields — the units differ (price-move /
    day / vol-point), so they must NOT be summed. Lives ALONGSIDE the locked
    VOL-GEX, does NOT replace it. Structural only — consumers MUST treat as
    experimental. See ``engine.total_hedging`` and
    docs/research/empirical/synthetic-oi-roadmap.md."""

    model_config = ConfigDict(extra="forbid")

    gamma_hedge: float
    """Gamma term on Q, USD per 1% price move (== synthetic-OI GEX at ``w``)."""
    charm_hedge: float
    """Charm term on Q, USD dealer dollar-delta drift per calendar day."""
    vanna_hedge: float
    """Vanna term on Q, USD dealer dollar-delta per 1% IV (vol-point)."""
    w: float = Field(ge=0, le=1)
    """Open/close flow weight in [0, 1] used for the ``Q`` base."""


class Surface(BaseModel):
    """Vol-surface summary — raw-SVI slice + expected move (EXPERIMENTAL).

    Optional/additive (mirrors ``total_hedging``/``exposure_ext``): ``None`` when not
    captured (fewer than 5 non-thin strikes), no ``schema_version`` bump. The fit is
    deterministic and tested, but it is NOT a price-validated signal. Carries the
    fitted raw-SVI params so a consumer can reconstruct the whole smile, plus the ATM
    vol, the 1-sigma lognormal expected move, the ATM skew and fit quality. See
    ``engine.surface`` and docs/research/empirical/synthetic-oi-0dte.md."""

    model_config = ConfigDict(extra="forbid")

    atm_vol: float
    """At-the-money implied vol (annualised, per 1.00) from the SVI fit at k=0."""
    expected_move: float
    """1-sigma lognormal expected move ``F·atm_vol·sqrt(T)``, index points."""
    skew: float
    """ATM skew: slope of SVI vol in log-moneyness (negative = put skew)."""
    rmse: float
    """Fit RMSE in vol units."""
    arb_free: bool
    """Gatheral sufficient no-butterfly conditions hold for the slice."""
    svi_a: float
    """Raw-SVI ``a`` (vertical level)."""
    svi_b: float
    """Raw-SVI ``b`` (slope/wing tightness, >= 0)."""
    svi_rho: float
    """Raw-SVI ``rho`` (skew/rotation, |rho| < 1)."""
    svi_m: float
    """Raw-SVI ``m`` (horizontal shift of smile minimum)."""
    svi_sigma: float
    """Raw-SVI ``sigma`` (ATM curvature smoothness, > 0)."""


class Ddoi(BaseModel):
    """Synthetic Dealer Directional OI GEX (EXPERIMENTAL — NOT price-validated).

    Optional/additive (mirrors ``synthetic_oi``/``exposure_ext``): ``None`` when not
    captured, no ``schema_version`` bump. An ALTERNATIVE GEX basis to the locked VOL:
    each trade is classified OPEN vs CLOSE from its intraday time position (early =
    opening, late = closing) to estimate a signed per-leg synthetic ΔOI, then driven
    through the SAME locked dealer-sign + gamma template. Non-circular (never reads
    official ΔOI), orthogonal to VOL. On the 8-day exploratory run it read FLAT vs
    VOL — the machine is sound, the edge is not proven. Lives ALONGSIDE the locked
    VOL-GEX, does NOT replace it. See ``engine.ddoi`` and
    docs/research/empirical/track-f-ddoi-exposure-vol.md."""

    model_config = ConfigDict(extra="forbid")

    gex: float
    """Net synthetic-ΔOI GEX, USD per 1% move. EXPERIMENTAL."""
    sign: RegimeSign
    """Sign of ``gex``: -1 | 0 | 1."""


class Snapshot(BaseModel):
    """Canonical per-(instrument, minute) snapshot object. PRD #8 §3."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    """Schema version. MUST equal SCHEMA_VERSION (1). PRD #8 §3."""
    instrument: Instrument
    """Instrument: "ES" | "NQ". PRD #0 §4."""
    session_date: str
    """Trading session date (America/New_York), ISO date YYYY-MM-DD. PRD #9."""
    ts: str
    """Snapshot timestamp, ISO-8601 datetime in UTC (…Z). PRD #8 §3."""
    minute_index: int
    """Minutes since RTH open; 0 = 09:30 ET. PRD #8 §3."""
    state: SessionState
    """Session state. PRD #9."""
    stale: bool
    """True when the feed is stale (1–2 min gap, last frame held). PRD #0 §2."""
    expired: bool
    """True once the 0DTE contracts for the session have expired. PRD #9."""
    forward: float
    """Forward = futures price F, in index points. PRD #0 §3."""
    rate: float
    """Continuous annual risk-free rate r = ln(1 + SOFR). PRD #0 §3–§4."""
    axis: Axis
    regime: Regime
    profile: list[ProfileRow]
    """Net GEX/DEX profile rows, ascending by strike. PRD #8 §3."""
    field: FieldGrid
    levels: Levels
    ohlc: OHLC | None = None
    """Underlying OHLC for this minute (candle view). None when not captured."""
    hiro: Hiro | None = None
    """Cumulative dealer hedging flow (HIRO). None when not captured. PRD FlowGreeks."""
    synthetic_oi: SyntheticOi | None = None
    """Synthetic-OI #4 positioning lens (EXPERIMENTAL). None when not captured."""
    synthetic_oi_tiered: SyntheticOi | None = None
    """Synthetic-OI #6 size-tiered lens (EXPERIMENTAL, same shape as #4). None when not captured."""
    synthetic_oi_decay: SyntheticOi | None = None
    """Synthetic-OI #5 decay-weighted lens (EXPERIMENTAL, same shape as #4). None when not captured."""
    exposure_ext: ExposureExt | None = None
    """Extended dealer exposure VEX/CHEX (EXPERIMENTAL). None when not captured."""
    total_hedging: TotalHedging | None = None
    """Synthetic-OI #7 total-hedging map (EXPERIMENTAL). None when not captured."""
    surface: Surface | None = None
    """Vol-surface summary (SVI + expected move, EXPERIMENTAL). None when not captured."""
    ddoi: Ddoi | None = None
    """Synthetic Dealer Directional OI GEX (EXPERIMENTAL). None when not captured."""

    @field_validator("session_date")
    @classmethod
    def _validate_session_date(cls, v: str) -> str:
        if not _DATE_RE.match(v):
            raise ValueError("session_date must be an ISO date YYYY-MM-DD")
        return v

    @field_validator("ts")
    @classmethod
    def _validate_ts(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("ts must be an ISO-8601 UTC datetime ending with 'Z'")
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("ts must be a valid ISO-8601 UTC datetime") from exc
        return v

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize to JSON with keys identical to the TypeScript contract."""
        return self.model_dump_json(indent=indent)


def parse_snapshot(data: object) -> Snapshot:
    """Validate and parse ``data`` (dict or JSON string) into a Snapshot.

    Raises ``pydantic.ValidationError`` on invalid input.
    """
    if isinstance(data, (str, bytes, bytearray)):
        return Snapshot.model_validate_json(data)
    return Snapshot.model_validate(data)
