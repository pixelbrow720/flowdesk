/**
 * Mock Snapshot fixtures for offline FE development (no backend required).
 *
 * Both fixtures are valid per @flowdesk/contracts (schema_version 1) and are
 * validated at module load via parseSnapshot, so an accidental drift from the
 * locked contract fails fast in dev. /ES uses strike step 5, /NQ uses step 10
 * (PRD #0 §4). Arrays in `field` are index-aligned and equal length (AC-A2).
 */
import { parseSnapshot, type Snapshot } from "@flowdesk/contracts";

// Build an index-aligned strike grid [min..max] inclusive, by step.
function strikeGrid(min: number, max: number, step: number): number[] {
  const out: number[] = [];
  for (let s = min; s <= max; s += step) out.push(s);
  return out;
}

interface SnapshotParts {
  price_grid: number[];
  gamma: number[];
  delta: number[];
  profile: Array<{
    strike: number;
    net_gex: number;
    net_dex: number;
    interpolated: boolean;
  }>;
}

/**
 * Build the index-aligned field arrays + profile rows in a single pass so the
 * parallel arrays never need unchecked indexing. The field is a smooth signed
 * shape: a positive hump near the forward, negative wings — "pinning at the
 * money, volatile in the tails".
 */
function buildParts(grid: number[], forward: number, scale: number): SnapshotParts {
  const first = grid[0] ?? forward;
  const last = grid[grid.length - 1] ?? forward;
  const span = last - first || 1;
  const n = grid.length;

  const rows = grid.map((strike, i) => {
    const d = (strike - forward) / span; // ~[-0.5, 0.5]
    const gamma = Math.round((1 - 18 * d * d) * scale);
    const delta = Math.round((1 - i / n) * scale * 0.6); // monotone decay
    return { strike, gamma, delta };
  });

  return {
    price_grid: rows.map((r) => r.strike),
    gamma: rows.map((r) => r.gamma),
    delta: rows.map((r) => r.delta),
    profile: rows.map((r, i) => ({
      strike: r.strike,
      net_gex: r.gamma * 12,
      net_dex: r.delta * 8,
      interpolated: i % 7 === 3,
    })),
  };
}

const ES_MIN = 4950;
const ES_MAX = 5050;
const esForward = 5000.25;
const esParts = buildParts(strikeGrid(ES_MIN, ES_MAX, 5), esForward, 33_000_000);
const ES_RAW = {
  schema_version: 1,
  instrument: "ES",
  session_date: "2026-06-10",
  ts: "2026-06-10T13:31:00Z",
  minute_index: 1,
  state: "LIVE",
  stale: false,
  expired: false,
  forward: esForward,
  rate: 0.0517,
  axis: { strike_min: ES_MIN, strike_max: ES_MAX, step: 5 },
  regime: { net_gamma: 560_000_000, sign: 1, stability_pct: 63.5 },
  profile: esParts.profile,
  field: { price_grid: esParts.price_grid, gamma: esParts.gamma, delta: esParts.delta },
  levels: {
    call_walls: [5050, 5025, 5015],
    put_walls: [4950, 4975, 4985],
    gamma_flip: 4998.5,
    largest_gex: 5000,
    largest_dex: 4990,
  },
};

const NQ_MIN = 17_800;
const NQ_MAX = 18_200;
const nqForward = 18_000.5;
const nqParts = buildParts(strikeGrid(NQ_MIN, NQ_MAX, 10), nqForward, 21_000_000);
const NQ_RAW = {
  schema_version: 1,
  instrument: "NQ",
  session_date: "2026-06-10",
  ts: "2026-06-10T13:31:00Z",
  minute_index: 1,
  state: "LIVE",
  stale: false,
  expired: false,
  forward: nqForward,
  rate: 0.0517,
  axis: { strike_min: NQ_MIN, strike_max: NQ_MAX, step: 10 },
  regime: { net_gamma: -812_000_000, sign: -1, stability_pct: 38.0 },
  profile: nqParts.profile,
  field: { price_grid: nqParts.price_grid, gamma: nqParts.gamma, delta: nqParts.delta },
  levels: {
    call_walls: [18200, 18100, 18050],
    put_walls: [17800, 17900, 17950],
    gamma_flip: 18010,
    largest_gex: 18000,
    largest_dex: 17900,
  },
};

/** Validated mock snapshots (throws at import if they drift from the contract). */
export const MOCK_SNAPSHOTS: Record<"ES" | "NQ", Snapshot> = {
  ES: parseSnapshot(ES_RAW),
  NQ: parseSnapshot(NQ_RAW),
};
