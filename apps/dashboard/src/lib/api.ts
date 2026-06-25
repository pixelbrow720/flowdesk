/**
 * FlowDesk dashboard — API host + endpoint resolution and the Snapshot shape.
 *
 * The dashboard is STANDALONE (its own node_modules + lockfile, NOT in the pnpm
 * workspace), so it cannot import `@flowdesk/contracts` directly without pulling
 * zod into this app. To keep the app dependency-light, the Snapshot type here is
 * a hand-mirror of the canonical contract (`packages/contracts/src/snapshot.ts`
 * == `services/engine/src/engine/schema.py`, schema_version 2). The contract
 * package remains the single source of truth — keep this in sync when fields
 * change (the optional/experimental blocks below mirror it 1:1).
 *
 * `NEXT_PUBLIC_API_BASE_URL` overrides the API host (staging/prod); default is
 * the local-dev API at http://localhost:8000, matching the landing app and the
 * repo `.env` `PUBLIC_BASE_URL`.
 */

const DEFAULT_API_BASE_URL = "http://localhost:8000";

/** API origin with any trailing slash stripped. */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

export type Instrument = "ES" | "NQ";

/** REST: latest Snapshot for an instrument (DESK-gated; 404 when none yet). */
export function snapshotUrlFor(instrument: Instrument): string {
  return `${API_BASE_URL}/api/snapshot?instrument=${instrument}`;
}

/** WS: live snapshot stream. Derives ws:// or wss:// from the API scheme. */
export function wsUrlFor(instrument: Instrument): string {
  const ws = API_BASE_URL.replace(/^http(s?):\/\//, (_m, s) => `ws${s}://`);
  return `${ws}/ws?instrument=${instrument}`;
}

/** WS: real-time tick stream for live candle updates (5s throttled). */
export function wsTicksUrlFor(instrument: Instrument): string {
  const ws = API_BASE_URL.replace(/^http(s?):\/\//, (_m, s) => `ws${s}://`);
  return `${ws}/ws/ticks?instrument=${instrument}`;
}

/** Static last-resort: a pre-generated full-session JSON under public/data. */
export function staticUrlFor(instrument: Instrument, date: string): string {
  return `/data/${instrument}_${date}.json`;
}

/* ------------------------------------------------------------------ */
/* Snapshot shape (mirror of @flowdesk/contracts, schema_version 2).   */
/* ------------------------------------------------------------------ */

export interface SnapshotProfileRow {
  strike: number;
  net_gex: number;
  net_dex: number;
  interpolated: boolean;
}

export interface SnapshotLevels {
  call_walls: number[];
  put_walls: number[];
  gamma_flip: number | null;
  largest_gex: number | null;
  largest_dex: number | null;
}

export interface SnapshotSurface {
  atm_vol: number;
  expected_move: number;
  skew: number;
  svi_a: number;
  svi_b: number;
  svi_rho: number;
  svi_m: number;
  svi_sigma: number;
}

export interface SnapshotProprietary {
  oi_gamma_flip: number | null;
  abs_gamma_strike: number | null;
  hedge_wall: number | null;
}

/** Per-strike call/put implied-vol smile point (EXPERIMENTAL, optional). */
export interface SnapshotIvSmilePoint {
  strike: number;
  call_iv: number | null;
  put_iv: number | null;
}

export interface SnapshotThetaDecay {
  net_theta: number;
  theta_sign: number;
}

export interface SnapshotMaxPain {
  strike: number | null;
}

export interface SnapshotVolExpansion {
  expansion: number | null;
}

export interface SnapshotExposureExt {
  net_vex: number;
  vex_sign: -1 | 0 | 1;
  net_chex: number;
  chex_sign: -1 | 0 | 1;
  /** Strike axis for per-strike decomposition. Thin strikes absent. Added 2026-06-19. */
  strikes?: number[];
  /** Per-strike VEX, index-aligned to `strikes`. EXPERIMENTAL. Added 2026-06-19. */
  vex_by_strike?: number[];
  /** Per-strike CHEX, index-aligned to `strikes`. EXPERIMENTAL. Added 2026-06-19. */
  chex_by_strike?: number[];
}

export interface SnapshotRegime {
  net_gamma: number;
  sign: number;
  stability_pct: number;
}

export interface SnapshotFlux {
  total: number;
  calls: number;
  puts: number;
  zerodte: number;
  retail: number;
}

export interface SnapshotFog {
  price_grid: number[];
  gamma: number[];
  delta: number[];
}

export interface Snapshot {
  schema_version?: number;
  instrument?: Instrument;
  ts: string;
  minute_index: number;
  forward: number;
  state?: string;
  stale?: boolean;
  profile: SnapshotProfileRow[];
  levels: SnapshotLevels;
  regime: SnapshotRegime;
  fog: SnapshotFog;
  flux: SnapshotFlux | null;
  surface: SnapshotSurface | null;
  proprietary: SnapshotProprietary | null;
  iv_smile?: SnapshotIvSmilePoint[] | null;
  theta_decay?: SnapshotThetaDecay | null;
  max_pain?: SnapshotMaxPain | null;
  vol_expansion?: SnapshotVolExpansion | null;
  exposure_ext?: SnapshotExposureExt | null;
  total_hedging?: {
    gamma_hedge: number;
    charm_hedge: number;
    vanna_hedge: number;
  } | null;
}

/**
 * Lightweight runtime guard — NOT full zod validation (the dashboard stays
 * dependency-light), just enough to reject obviously-wrong payloads before they
 * reach the pure chart builders. Mirrors the fields those builders read.
 */
export function isSnapshot(value: unknown): value is Snapshot {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.ts === "string" &&
    typeof v.forward === "number" &&
    Array.isArray(v.profile) &&
    typeof v.regime === "object" &&
    v.regime !== null &&
    typeof v.levels === "object" &&
    v.levels !== null
  );
}
