/**
 * Live-tape data shapes mirrored from packages/contracts/src/snapshot.ts
 * (schema_version 2). Landing renders STATIC EXHIBIT samples — real payloads
 * will be wired in via /api/snapshot once the engine is gated.
 */

export type Instrument = 'ES' | 'NQ';

export interface ExhibitTick {
  ts: string;
  forward: number;
  flux: number;
  fog_peak: number;
  regime_stability: number;
}

export const EXHIBIT_A: ExhibitTick[] = [
  { ts: '2026-06-10T13:31:00Z', forward: 5004.25, flux:  +1_240_000, fog_peak: 5005, regime_stability: 0.62 },
  { ts: '2026-06-10T13:32:00Z', forward: 5005.50, flux:  +2_180_000, fog_peak: 5005, regime_stability: 0.64 },
  { ts: '2026-06-10T13:33:00Z', forward: 5006.75, flux:  +3_410_000, fog_peak: 5005, regime_stability: 0.61 },
  { ts: '2026-06-10T13:34:00Z', forward: 5006.25, flux:  +2_950_000, fog_peak: 5005, regime_stability: 0.59 },
  { ts: '2026-06-10T13:35:00Z', forward: 5004.00, flux:  +1_120_000, fog_peak: 5005, regime_stability: 0.55 },
  { ts: '2026-06-10T13:36:00Z', forward: 5001.50, flux:    -340_000, fog_peak: 5000, regime_stability: 0.48 },
  { ts: '2026-06-10T13:37:00Z', forward: 4998.75, flux:  -2_010_000, fog_peak: 5000, regime_stability: 0.41 },
  { ts: '2026-06-10T13:38:00Z', forward: 4997.25, flux:  -3_220_000, fog_peak: 4995, regime_stability: 0.37 },
];

export const MANIFESTO = [
  { n: '001', title: 'Retail charts lie about who is buying.',
    body: 'Volume bars do not distinguish dealer hedge flow from speculative intent. Most platforms collapse both into one number. Operators trade the difference.' },
  { n: '002', title: 'Greeks are not a heatmap.',
    body: 'Static gamma walls lag price by hours. Real exposure breathes minute by minute as forward, IV, and rate move. A snapshot must respect that.' },
  { n: '003', title: 'Lenses must be honest.',
    body: 'Some signals are research, not law. We surface every experimental lens with NOT-VALIDATED tags. You see the ground truth, not a marketing curve.' },
  { n: '004', title: 'Latency is a feature.',
    body: 'A snapshot late by 90 seconds is a different instrument. Build, fixture, golden — every commit ships with a frozen contract and a stamped ts.' },
];

export const LENSES = [
  { key: 'FLUX', title: 'FLUX', subtitle: 'Cumulative dealer hedging flow',
    body: 'Signed USD flow per minute. Positive = dealers net buying delta into the move. Negative = unwinding. Source of trend conviction when separated from speculative tape.',
    status: 'PRODUCTION' as const },
  { key: 'FOG', title: 'FOG', subtitle: 'Heatmap field projection',
    body: 'Gamma + delta arrays sampled across the strike axis, clamped to finite. Renders as a breathing topography — high-density zones pin price, low-density zones release it.',
    status: 'PRODUCTION' as const },
  { key: 'EXHIBIT_A', title: 'EXHIBIT A', subtitle: 'Locked golden snapshot',
    body: 'Every release pins a byte-exact reference snapshot. The engine fixture, the contract fixture, and the test fixture move in lockstep. Schema bumps are explicit.',
    status: 'PRODUCTION' as const },
  { key: 'LEVELS', title: 'LEVELS', subtitle: 'Call/put walls + gamma flip',
    body: 'Discrete key levels overlaid on the field. Walls = strikes where dealer exposure peaks. Flip = the strike where net gamma changes sign.',
    status: 'PRODUCTION' as const },
  { key: 'SYNTHETIC_OI', title: 'SYNTHETIC OI', subtitle: 'Inferred positioning lens',
    body: 'Three flavors — raw, size-tiered, decay-weighted. Decompose volume into best-guess open interest changes when the exchange does not publish them in real time.',
    status: 'NOT-VALIDATED' as const },
  { key: 'EXPOSURE_EXT', title: 'EXPOSURE EXT', subtitle: 'VEX + CHEX dealer exposure',
    body: 'Vol-of-vol exposure and charm exposure. Captures the second-order hedging that GEX alone misses. Surfaces only when the surface fit converges.',
    status: 'NOT-VALIDATED' as const },
  { key: 'SURFACE', title: 'SURFACE', subtitle: 'SVI + expected move',
    body: 'Deterministic Nelder-Mead SVI fit per minute. Computed only when ≥5 non-thin strikes are available. Otherwise null — never extrapolated to fill the screen.',
    status: 'NOT-VALIDATED' as const },
];

export const HONESTY_LEDGER = [
  { claim: 'FLUX = dealer hedge flow',          status: 'PRODUCTION',    note: 'Black-76 + dealer +1/-1 sign convention' },
  { claim: 'FOG = gamma/delta heatmap',         status: 'PRODUCTION',    note: 'Element-finite enforced ingress + egress' },
  { claim: 'GEX scale = 0.01 (per 1% move)',    status: 'LOCKED',        note: 'docs/02-locked-contract.md' },
  { claim: 'schema_version 2',                  status: 'BREAKING-OK',   note: 'mirror trio bumped lockstep 2026-06-15' },
  { claim: 'Synthetic OI 3-tier',               status: 'NOT-VALIDATED', note: 'research lens, surface in product behind tag' },
  { claim: 'VEX/CHEX exposure',                 status: 'NOT-VALIDATED', note: 'sensitive to fit convergence' },
  { claim: 'SVI surface fit',                   status: 'NOT-VALIDATED', note: 'null when <5 non-thin strikes' },
  { claim: 'Live feed',                         status: 'GATED',         note: 'paid beta = FEED_MODE=historical only' },
];

export const PERF_TARGETS = [
  { metric: 'LCP',  target: '≤2.0s',  actual: 'TBD' },
  { metric: 'CLS',  target: '≤0.05',  actual: 'TBD' },
  { metric: 'INP',  target: '≤150ms', actual: 'TBD' },
  { metric: 'JS',   target: '≤100KB', actual: 'TBD' },
];

export const LATENCY_BUDGET_MS = 90;
