/**
 * FlowDesk — canonical Snapshot data contract (schema_version 1).
 *
 * SINGLE SOURCE OF TRUTH for the per-(instrument, minute) snapshot object that
 * the compute engine produces, the API serves, and the frontend renders. The
 * Python mirror lives at `services/engine/src/engine/schema.py` and MUST stay
 * 1:1 with these field names and semantics.
 *
 * Units & meanings are taken from PRD #0 (Glossary & Global Contract) and the
 * canonical schema in PRD #8 §3. See `CONTRACT.md` for the field-by-field map.
 *
 * BREAKING CHANGES: any change to a field name, type, or meaning REQUIRES
 * bumping `SCHEMA_VERSION` (and the Python mirror) in lockstep.
 */

import { z } from "zod";

/** Canonical schema version. Bump on ANY breaking change. */
export const SCHEMA_VERSION = 1 as const;
/** Type of the canonical schema version literal. */
export type SchemaVersion = typeof SCHEMA_VERSION;

/** Tradable instrument. /ES (M=$50/pt, step 5) or /NQ (M=$20/pt, step 10). PRD #0 §4. */
export type Instrument = "ES" | "NQ";

/**
 * Session state machine value (PRD #9, PRD #8 §3).
 * - PREMARKET: before RTH open (09:30 ET).
 * - LIVE: streaming inside RTH.
 * - STALE: feed gap of 1–2 minutes; last frame held (PRD #0 §2).
 * - CLOSED: after RTH close (16:00 ET) on a trading day.
 * - HOLIDAY: CME holiday / non-trading day.
 */
export type SessionState =
  | "PREMARKET"
  | "LIVE"
  | "STALE"
  | "CLOSED"
  | "HOLIDAY";

/** Sign of net gamma. -1 negative (crimson/volatile), 0 flat, +1 positive (turquoise/pinning). PRD #0 §6. */
export type RegimeSign = -1 | 0 | 1;

/** Strike axis bounds shared by the profile and the heatmap field. */
export interface Axis {
  /** Lowest strike on the shared axis, in index points. PRD #8 §3. */
  strike_min: number;
  /** Highest strike on the shared axis, in index points. PRD #8 §3. */
  strike_max: number;
  /** Strike increment in index points (/ES = 5, /NQ = 10). PRD #0 §4. */
  step: number;
}

/** Market regime summary (PRD #4 v1 = sign of net gamma + stability %). */
export interface Regime {
  /** Aggregate dealer net gamma exposure, USD per 1% move. PRD #0 §5–§6. */
  net_gamma: number;
  /** Sign of `net_gamma`: -1 | 0 | 1. PRD #0 §6. */
  sign: RegimeSign;
  /** Regime stability, percent in [0, 100]. PRD #0 §2 (Stability %). */
  stability_pct: number;
}

/** One strike row of the Net GEX/DEX profile (left panel). PRD #8 §3. */
export interface ProfileRow {
  /** Strike, in index points. */
  strike: number;
  /** Net dealer Gamma Exposure at this strike, USD per 1% move. PRD #0 §5. */
  net_gex: number;
  /** Net dealer Delta Exposure at this strike, USD notional. PRD #0 §2. */
  net_dex: number;
  /** True if this strike's values were interpolated (synthetic) vs observed. PRD #8 §3. */
  interpolated: boolean;
}

/**
 * Heatmap field projection arrays (right panel). All three arrays are
 * index-aligned and MUST share the same length: `price_grid[i]` corresponds to
 * `gamma[i]` and `delta[i]`. PRD #8 §3 (AC-A2).
 */
export interface FieldGrid {
  /** Price grid (index points) defining the field's price axis. PRD #8 §3. */
  price_grid: number[];
  /** Gamma field value at each `price_grid` point, USD per 1% move. PRD #0 §5. */
  gamma: number[];
  /** Delta field value at each `price_grid` point, USD notional. PRD #8 §3. */
  delta: number[];
}

/** Key levels overlay. PRD #0 §2, locked contract. */
export interface Levels {
  /** Call walls by OI, STATIC all day, ordered by rank (index 0 = rank 1). Strikes in index points. PRD #0 §2. */
  call_walls: number[];
  /** Put walls by OI, STATIC all day, ordered by rank (index 0 = rank 1). Strikes in index points. PRD #0 §2. */
  put_walls: number[];
  /** Gamma flip strike (net-gamma zero-crossing), by VOL, dynamic. Index points, or null if none. PRD #0 §2. */
  gamma_flip: number | null;
  /** Strike of the largest GEX by VOL, dynamic. Index points, or null. PRD #0 §2. */
  largest_gex: number | null;
  /** Strike of the largest DEX by VOL, dynamic. Index points, or null. PRD #0 §2. */
  largest_dex: number | null;
}

/** Underlying (futures forward) OHLC for this minute. PRD #4 candle view. */
export interface OHLC {
  /** Open: first futures trade price in the minute, index points. */
  o: number;
  /** High: max futures trade price in the minute. */
  h: number;
  /** Low: min futures trade price in the minute. */
  l: number;
  /** Close: last futures trade price in the minute (== forward). */
  c: number;
}

/**
 * Cumulative dealer delta-notional hedging flow since the RTH open (HIRO).
 * Optional/additive (Divergence #5 -> option A): absent for snapshots produced
 * before HIRO was wired, mirroring the `ohlc` precedent — does NOT bump
 * `SCHEMA_VERSION`. Units are USD delta-notional; positive = net dealer BUYING
 * pressure (bullish), negative = selling pressure.
 */
export interface Hiro {
  /** Cumulative HIRO (all legs), USD delta-notional since RTH open. */
  total: number;
  /** Cumulative HIRO from call trades only, USD delta-notional. */
  calls: number;
  /** Cumulative HIRO from put trades only, USD delta-notional. */
  puts: number;
  /** Cumulative HIRO from 0DTE trades (T < 1/365), USD delta-notional. */
  zerodte: number;
  /** Cumulative HIRO from the (heuristic) retail proxy, USD delta-notional. */
  retail: number;
}

/**
 * Synthetic-OI #4 positioning lens (EXPERIMENTAL — NOT price-validated).
 * Optional/additive (mirrors `hiro`/`ohlc`): absent when not captured, does NOT
 * bump `SCHEMA_VERSION`. Dealer position = carried-in open interest (static
 * long-call/short-put sign) updated by native CME aggressor-signed flow, weighted
 * by `w`. Lives alongside the locked VOL-based GEX; does NOT replace it. Validated
 * only structurally on a 4-day sample — treat as experimental, not authoritative.
 */
export interface SyntheticOi {
  /** Net synthetic-OI GEX at weight `w`, USD per 1% move. EXPERIMENTAL. */
  gex: number;
  /** Sign of `gex`: -1 | 0 | 1. */
  sign: RegimeSign;
  /** w=0 pure-OI GEX baseline (SpotGamma-classic), USD per 1% move. */
  gex_static: number;
  /** Open/close flow weight in [0, 1] used for `gex`. */
  w: number;
}

/**
 * Extended dealer exposure — VEX (vanna) + CHEX (charm). EXPERIMENTAL.
 *
 * Optional/additive (mirrors `hiro`/`synthetic_oi`): null when not captured, no
 * schema_version bump. Same VOL basis + locked dealer signs as the product
 * GEX/DEX; lives alongside them, does NOT replace them. FD-validated greeks, but
 * the aggregate is NOT price-validated — treat as experimental, not authoritative.
 * NOTE units differ from GEX: `net_vex` is per 1% IV (a vol-point scale), NOT per
 * 1% price move; `net_chex` is per calendar day.
 */
export interface ExposureExt {
  /** Net vanna exposure, USD dealer dollar-delta per 1% IV move. EXPERIMENTAL. */
  net_vex: number;
  /** Sign of `net_vex`: -1 | 0 | 1. */
  vex_sign: RegimeSign;
  /** Net charm exposure, USD dealer dollar-delta per calendar day. EXPERIMENTAL. */
  net_chex: number;
  /** Sign of `net_chex`: -1 | 0 | 1. */
  chex_sign: RegimeSign;
}

/**
 * Synthetic-OI #7 total-hedging map — gamma + charm + vanna on the Q base.
 * EXPERIMENTAL.
 *
 * Optional/additive (mirrors `synthetic_oi`/`exposure_ext`): null when not
 * captured, no schema_version bump. Applies all three hedging greeks to the SAME
 * synthetic dealer position Q as synthetic-OI #4 (dealer sign baked in). THREE
 * SEPARATE fields — units differ (price-move / day / vol-point), so they must NOT
 * be summed. Lives alongside the locked VOL-GEX, does NOT replace it. Structural
 * only — treat as experimental, not authoritative.
 */
export interface TotalHedging {
  /** Gamma term on Q, USD per 1% price move (== synthetic-OI GEX at `w`). */
  gamma_hedge: number;
  /** Charm term on Q, USD dealer dollar-delta drift per calendar day. */
  charm_hedge: number;
  /** Vanna term on Q, USD dealer dollar-delta per 1% IV (vol-point). */
  vanna_hedge: number;
  /** Open/close flow weight in [0, 1] used for the Q base. */
  w: number;
}

/**
 * Vol-surface summary — raw-SVI slice + expected move. EXPERIMENTAL.
 *
 * Optional/additive (mirrors `total_hedging`/`exposure_ext`): null when not
 * captured (fewer than 5 non-thin strikes), no schema_version bump. The fit is
 * deterministic and tested, but NOT a price-validated signal. Carries the fitted
 * raw-SVI params (so a consumer can reconstruct the whole smile), the ATM vol, the
 * 1-sigma lognormal expected move, the ATM skew and fit quality.
 */
export interface Surface {
  /** At-the-money implied vol (annualised, per 1.00) from the SVI fit at k=0. */
  atm_vol: number;
  /** 1-sigma lognormal expected move `F*atm_vol*sqrt(T)`, index points. */
  expected_move: number;
  /** ATM skew: slope of SVI vol in log-moneyness (negative = put skew). */
  skew: number;
  /** Fit RMSE in vol units. */
  rmse: number;
  /** Gatheral sufficient no-butterfly conditions hold for the slice. */
  arb_free: boolean;
  /** Raw-SVI `a` (vertical level). */
  svi_a: number;
  /** Raw-SVI `b` (slope/wing tightness, >= 0). */
  svi_b: number;
  /** Raw-SVI `rho` (skew/rotation, |rho| < 1). */
  svi_rho: number;
  /** Raw-SVI `m` (horizontal shift of smile minimum). */
  svi_m: number;
  /** Raw-SVI `sigma` (ATM curvature smoothness, > 0). */
  svi_sigma: number;
}

/** The canonical per-(instrument, minute) snapshot object. PRD #8 §3. */
export interface Snapshot {
  /** Schema version. MUST equal `SCHEMA_VERSION` (1). PRD #8 §3. */
  schema_version: SchemaVersion;
  /** Instrument: "ES" | "NQ". PRD #0 §4. */
  instrument: Instrument;
  /** Trading session date (America/New_York), ISO date "YYYY-MM-DD". PRD #9. */
  session_date: string;
  /** Snapshot timestamp, ISO-8601 datetime in UTC (…Z). PRD #8 §3. */
  ts: string;
  /** Minutes since RTH open; 0 = 09:30 ET. Integer. PRD #8 §3. */
  minute_index: number;
  /** Session state. PRD #9. */
  state: SessionState;
  /** True when the feed is stale (1–2 min gap, last frame held). PRD #0 §2. */
  stale: boolean;
  /** True once the 0DTE contracts for the session have expired. PRD #9. */
  expired: boolean;
  /** Forward = futures price F, in index points. PRD #0 §3. */
  forward: number;
  /** Continuous annual risk-free rate r = ln(1 + SOFR). PRD #0 §3–§4. */
  rate: number;
  /** Shared strike axis. */
  axis: Axis;
  /** Regime summary. */
  regime: Regime;
  /** Net GEX/DEX profile rows, ascending by `strike`. PRD #8 §3. */
  profile: ProfileRow[];
  /** Heatmap field projection arrays. */
  field: FieldGrid;
  /** Key levels overlay. */
  levels: Levels;
  /** Underlying OHLC for this minute (candle view). null when not captured. */
  ohlc?: OHLC | null;
  /** Cumulative dealer hedging flow (HIRO). null when not captured. */
  hiro?: Hiro | null;
  /** Synthetic-OI #4 positioning lens (EXPERIMENTAL). null when not captured. */
  synthetic_oi?: SyntheticOi | null;
  /** Synthetic-OI #6 size-tiered lens (EXPERIMENTAL, same shape as #4). null when not captured. */
  synthetic_oi_tiered?: SyntheticOi | null;
  /** Extended dealer exposure VEX/CHEX (EXPERIMENTAL). null when not captured. */
  exposure_ext?: ExposureExt | null;
  /** Synthetic-OI #7 total-hedging map (EXPERIMENTAL). null when not captured. */
  total_hedging?: TotalHedging | null;
  /** Vol-surface summary (SVI + expected move, EXPERIMENTAL). null when not captured. */
  surface?: Surface | null;
}

/* ────────────────────── Runtime validators (zod) ────────────────────── */

/** "ES" | "NQ" */
export const InstrumentSchema = z.enum(["ES", "NQ"]);
/** Session state enum. */
export const SessionStateSchema = z.enum([
  "PREMARKET",
  "LIVE",
  "STALE",
  "CLOSED",
  "HOLIDAY",
]);
/** -1 | 0 | 1 */
export const RegimeSignSchema = z.union([
  z.literal(-1),
  z.literal(0),
  z.literal(1),
]);

const finiteNumber = z.number().finite();
const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "session_date must be an ISO date YYYY-MM-DD");
const isoDateTimeUtc = z.string().datetime();

/** Runtime schema for {@link Axis}. */
export const AxisSchema = z
  .object({
    strike_min: finiteNumber,
    strike_max: finiteNumber,
    step: finiteNumber.positive(),
  })
  .strict();

/** Runtime schema for {@link Regime}. */
export const RegimeSchema = z
  .object({
    net_gamma: finiteNumber,
    sign: RegimeSignSchema,
    stability_pct: z.number().min(0).max(100),
  })
  .strict();

/** Runtime schema for {@link ProfileRow}. */
export const ProfileRowSchema = z
  .object({
    strike: finiteNumber,
    net_gex: finiteNumber,
    net_dex: finiteNumber,
    interpolated: z.boolean(),
  })
  .strict();

/**
 * Runtime schema for {@link FieldGrid}. Enforces the array-length invariants:
 * `price_grid` defines the grid, so `gamma.length === delta.length === price_grid.length`.
 */
export const FieldSchema = z
  .object({
    price_grid: z.array(finiteNumber),
    gamma: z.array(finiteNumber),
    delta: z.array(finiteNumber),
  })
  .strict()
  .superRefine((f, ctx) => {
    if (f.gamma.length !== f.delta.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["delta"],
        message: `field.delta length (${f.delta.length}) must equal field.gamma length (${f.gamma.length})`,
      });
    }
    if (f.price_grid.length !== f.gamma.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["gamma"],
        message: `field.gamma length (${f.gamma.length}) must equal field.price_grid length (${f.price_grid.length})`,
      });
    }
  });

/** Runtime schema for {@link Levels}. */
export const LevelsSchema = z
  .object({
    call_walls: z.array(finiteNumber),
    put_walls: z.array(finiteNumber),
    gamma_flip: finiteNumber.nullable(),
    largest_gex: finiteNumber.nullable(),
    largest_dex: finiteNumber.nullable(),
  })
  .strict();

/** Runtime schema for {@link OHLC}. */
export const OHLCSchema = z
  .object({
    o: finiteNumber,
    h: finiteNumber,
    l: finiteNumber,
    c: finiteNumber,
  })
  .strict();

/** Runtime schema for {@link Hiro}. */
export const HiroSchema = z
  .object({
    total: finiteNumber,
    calls: finiteNumber,
    puts: finiteNumber,
    zerodte: finiteNumber,
    retail: finiteNumber,
  })
  .strict();

/** Runtime schema for {@link SyntheticOi}. */
export const SyntheticOiSchema = z
  .object({
    gex: finiteNumber,
    sign: RegimeSignSchema,
    gex_static: finiteNumber,
    w: z.number().min(0).max(1),
  })
  .strict();

/** Runtime schema for {@link ExposureExt}. */
export const ExposureExtSchema = z
  .object({
    net_vex: finiteNumber,
    vex_sign: RegimeSignSchema,
    net_chex: finiteNumber,
    chex_sign: RegimeSignSchema,
  })
  .strict();

/** Runtime schema for {@link TotalHedging}. */
export const TotalHedgingSchema = z
  .object({
    gamma_hedge: finiteNumber,
    charm_hedge: finiteNumber,
    vanna_hedge: finiteNumber,
    w: z.number().min(0).max(1),
  })
  .strict();

/** Runtime schema for {@link Surface}. */
export const SurfaceSchema = z
  .object({
    atm_vol: finiteNumber,
    expected_move: finiteNumber,
    skew: finiteNumber,
    rmse: finiteNumber,
    arb_free: z.boolean(),
    svi_a: finiteNumber,
    svi_b: finiteNumber,
    svi_rho: finiteNumber,
    svi_m: finiteNumber,
    svi_sigma: finiteNumber,
  })
  .strict();

/** Runtime schema for the full {@link Snapshot}. */
export const SnapshotSchema = z
  .object({
    schema_version: z.literal(SCHEMA_VERSION),
    instrument: InstrumentSchema,
    session_date: isoDate,
    ts: isoDateTimeUtc,
    minute_index: z.number().int(),
    state: SessionStateSchema,
    stale: z.boolean(),
    expired: z.boolean(),
    forward: finiteNumber,
    rate: finiteNumber,
    axis: AxisSchema,
    regime: RegimeSchema,
    profile: z.array(ProfileRowSchema),
    field: FieldSchema,
    levels: LevelsSchema,
    ohlc: OHLCSchema.nullish(),
    hiro: HiroSchema.nullish(),
    synthetic_oi: SyntheticOiSchema.nullish(),
    synthetic_oi_tiered: SyntheticOiSchema.nullish(),
    exposure_ext: ExposureExtSchema.nullish(),
    total_hedging: TotalHedgingSchema.nullish(),
    surface: SurfaceSchema.nullish(),
  })
  .strict();

/**
 * Parse and validate an unknown value into a {@link Snapshot}.
 * Throws `ZodError` on invalid input.
 */
export function parseSnapshot(input: unknown): Snapshot {
  return SnapshotSchema.parse(input);
}

/**
 * Non-throwing variant of {@link parseSnapshot}.
 * Returns a discriminated `{ success, data | error }` result.
 */
export function safeParseSnapshot(
  input: unknown,
): z.SafeParseReturnType<unknown, Snapshot> {
  return SnapshotSchema.safeParse(input);
}

/* ───────── Compile-time guarantee that the schemas never drift ───────── */

type Equals<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2
    ? true
    : false;
type Expect<T extends true> = T;

/**
 * Compile-time invariants: this tuple fails to type-check if any zod schema
 * and its TypeScript interface diverge. Exported so it is a "used" reference
 * (satisfies `noUnusedLocals`) and self-documents the locked snapshot contract.
 */
export type SchemaContractInvariants = [
  Expect<Equals<z.infer<typeof AxisSchema>, Axis>>,
  Expect<Equals<z.infer<typeof RegimeSchema>, Regime>>,
  Expect<Equals<z.infer<typeof ProfileRowSchema>, ProfileRow>>,
  Expect<Equals<z.infer<typeof FieldSchema>, FieldGrid>>,
  Expect<Equals<z.infer<typeof OHLCSchema>, OHLC>>,
  Expect<Equals<z.infer<typeof HiroSchema>, Hiro>>,
  Expect<Equals<z.infer<typeof SyntheticOiSchema>, SyntheticOi>>,
  Expect<Equals<z.infer<typeof ExposureExtSchema>, ExposureExt>>,
  Expect<Equals<z.infer<typeof TotalHedgingSchema>, TotalHedging>>,
  Expect<Equals<z.infer<typeof SurfaceSchema>, Surface>>,
  Expect<Equals<z.infer<typeof LevelsSchema>, Levels>>,
  Expect<Equals<z.infer<typeof SnapshotSchema>, Snapshot>>,
];
