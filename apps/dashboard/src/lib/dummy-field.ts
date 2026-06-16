/**
 * Synthetic GEX field generator for FOG dummy data.
 *
 * Real source-of-truth (data wiring phase) =
 *   Databento GLBX.MDP3 → Black-76 gamma per (strike, expiry) →
 *   dealer-sign model → grid V(strike, time) di $ notional.
 *
 * Until then this fakes a plausible field from the same dummy walls/profile
 * the rest of FOG already uses.
 *
 * Field convention (matches docs/reference/reverse-engineering-trace-gamma-heatmap.md §2):
 *   - Y axis = strike (rows)
 *   - X axis = time (cols)
 *   - Cell value = signed γ$ at that (strike, time)
 *   - Positive = long-gamma zone (dealers stabilize, blue/turquoise in colormap)
 *   - Negative = short-gamma zone (dealers amplify vol, brick/red in colormap)
 */

export type GexField = {
  values: Float32Array; // length = rows * cols, row-major (top row = highest strike)
  rows: number;
  cols: number;
  strikeMin: number;
  strikeMax: number;
  strikeStep: number;
  tStart: number; // ms epoch
  tEnd: number;
  absMax: number; // for symmetric clamping in the colormap
};

type Wall = { strike: number; gammaDollar: number };
type ProfileStrike = { strike: number; gamma: number };

/**
 * Generate a strike × time GEX field by smearing the per-strike gamma profile
 * forward in time, with two perturbations:
 *   1) Walls drift slightly across the session (intraday OI rebalances)
 *   2) Light noise so the heatmap doesn't look like a flat extrusion
 */
export function generateGexField(opts: {
  spot: number;
  callWalls: Wall[];
  putWalls: Wall[];
  gammaProfile: ProfileStrike[];
  rows?: number; // strikes
  cols?: number; // time bins
  sessionMinutes?: number;
}): GexField {
  const sessionMinutes = opts.sessionMinutes ?? 120;
  const cols = opts.cols ?? sessionMinutes; // 1 col per minute by default
  const strikeStep = 5;
  const profileStrikes = opts.gammaProfile.map((p) => p.strike);
  const strikeMin = Math.min(...profileStrikes);
  const strikeMax = Math.max(...profileStrikes);
  const rows = opts.rows ?? Math.round((strikeMax - strikeMin) / strikeStep) + 1;

  const tEnd = Date.now();
  const tStart = tEnd - sessionMinutes * 60_000;

  // Map strike → base gamma (from per-strike profile)
  const baseGamma = new Map<number, number>();
  for (const p of opts.gammaProfile) baseGamma.set(p.strike, p.gamma);

  // Wall contribution as Gaussian bumps centered on each wall strike, signed
  const wallSources: Array<{ strike: number; mag: number; sign: number }> = [
    ...opts.callWalls.map((w) => ({
      strike: w.strike,
      mag: w.gammaDollar,
      sign: +1,
    })),
    ...opts.putWalls.map((w) => ({
      strike: w.strike,
      mag: w.gammaDollar,
      sign: -1,
    })),
  ];

  const sigmaStrike = 12; // Gaussian width in price units (smooths walls vertically)
  const values = new Float32Array(rows * cols);

  for (let row = 0; row < rows; row++) {
    // row 0 = highest strike (top of chart)
    const strike = strikeMax - row * strikeStep;
    const base = baseGamma.get(strike) ?? 0;

    for (let col = 0; col < cols; col++) {
      const tFrac = col / Math.max(cols - 1, 1); // 0 → 1 across session

      // Walls drift slightly: each wall has a small sinusoidal nudge in strike
      let wallContribution = 0;
      for (let w = 0; w < wallSources.length; w++) {
        const src = wallSources[w];
        const drift = Math.sin(tFrac * Math.PI * 2 + w * 0.7) * 4; // ±4 pts
        const dist = strike - (src.strike + drift);
        const gauss = Math.exp(-(dist * dist) / (2 * sigmaStrike * sigmaStrike));
        wallContribution += src.sign * src.mag * gauss * 0.6;
      }

      // Mild temporal modulation on base gamma (intraday OI rebalance)
      const modulate = 1 + Math.sin(tFrac * Math.PI * 1.7 + row * 0.05) * 0.08;
      const noise =
        (Math.sin(row * 0.91 + col * 0.37) +
          Math.cos(row * 0.31 - col * 0.61) * 0.6) *
        0.04 *
        Math.max(Math.abs(base), 1e8);

      values[row * cols + col] = base * modulate + wallContribution + noise;
    }
  }

  // Symmetric clamping anchor for the colormap (P98 of |values|)
  const absSorted = Array.from(values, (v) => Math.abs(v)).sort((a, b) => a - b);
  const absMax = absSorted[Math.floor(absSorted.length * 0.98)] || 1;

  return {
    values,
    rows,
    cols,
    strikeMin,
    strikeMax,
    strikeStep,
    tStart,
    tEnd,
    absMax,
  };
}

/**
 * Synthetic session high/low — the intraday range reached so far.
 * Real source: rolling max/min of price ticks since RTH open.
 */
export function generateSessionRange(spot: number) {
  return {
    sessionHigh: spot + 7.5,
    sessionLow: spot - 11.25,
  };
}

/**
 * Synthetic secondary line — typically a smoothed/lagged reference
 * (e.g. 20-period SMA of price). Returned as bars with same time grid as candles.
 *
 * Caller passes the candles; this returns equal-length series.
 */
export function generateSecondaryLine(
  candles: Array<{ t: number; c: number }>,
  window = 20
): Array<{ t: number; v: number }> {
  const out: Array<{ t: number; v: number }> = [];
  for (let i = 0; i < candles.length; i++) {
    const lo = Math.max(0, i - window + 1);
    let sum = 0;
    let n = 0;
    for (let j = lo; j <= i; j++) {
      sum += candles[j].c;
      n++;
    }
    out.push({ t: candles[i].t, v: sum / n });
  }
  return out;
}
