# 04 — The Engine (`flowdesk-engine`)

The engine is the brain. It turns a chain of option quotes/trades plus a forward
and a rate into a single `Snapshot`. It is pure, deterministic, and calendar-free.

Source: `services/engine/src/engine/`.

## Pipeline

```
chain + forward + rate + session_state
   │
   ├─ black76.py    closed-form Black-76 price + greeks (delta, gamma, vanna, charm)
   ├─ iv.py         implied vol from mid (Newton → bisection, tol 1e-6)
   ├─ exposure.py   per-strike net GEX / net DEX (VOL-based, dealer-signed)
   ├─ field.py      price×strike projection grid (numpy + scipy)
   ├─ levels.py     call/put walls, gamma flip, largest GEX/DEX
   ├─ hiro.py       optional signed order-flow aggregate
   ├─ synthetic_oi.py  optional OI-anchored + flow-update GEX lens (EXPERIMENTAL)
   ├─ exposure_ext.py  optional VEX/CHEX (vanna/charm) aggregation (EXPERIMENTAL)
   ├─ total_hedging.py optional #7 gamma+charm+vanna on the synthetic-OI Q base (EXPERIMENTAL)
   ├─ surface.py    optional SVI fit + expected-move surface summary (EXPERIMENTAL)
   └─ snapshot.py   assembles + validates the canonical Snapshot
```

## Module by module

### `black76.py`
Closed-form **Black-76** on the future. Provides price, delta, gamma, and also
**vanna** and **charm**. Stdlib-only. The vanna/charm functions are implemented
and tested but **not yet aggregated** into the Snapshot (see `surface.py` and
[`08-status-and-gaps.md`](08-status-and-gaps.md)).

### `iv.py`
Implied vol from the **mid** price. **Newton** with a **bisection** fallback,
tolerance **1e-6**. Robust to the degenerate ends of the 0DTE chain.

### `exposure.py` — the core (and the most opinionated module)
Computes per-strike net exposure using the **locked VOL basis** and the
**hardcoded dealer sign** (long call / short put):

```
DEALER_SIGN_CALL = +1
DEALER_SIGN_PUT  = -1
net_gex(strike) = (SIGN_C·γ_call·vol_call + SIGN_P·γ_put·vol_put) · M · F² · 0.01
net_dex(strike) = (SIGN_C·δ_call·vol_call + SIGN_P·δ_put·vol_put) · M · F
```

`vol` is **cumulative volume since RTH open**. This is the deliberate
methodology choice (decision #1 — see `reference/methodology-decisions.md`): a
fixed dealer sign applied to traded volume, **not** a reconstructed dealer
position from signed flow or ΔOI. Its limitations are documented honestly in
[`08-status-and-gaps.md`](08-status-and-gaps.md) — this is the methodological weak point.

### `field.py`
The only numpy + scipy module. Projects per-strike exposure onto a **price ×
strike grid** (the heatmap source), producing `price_grid`, `gamma`, `delta`
arrays of equal length. Vectorized for performance.

### `levels.py`
Extracts the headline levels:
- **Call/Put walls** — gamma-dollar (`gamma·OI` per side), static, **Top-3** (decision #2).
- **Gamma flip** — the strike/price where net gamma crosses zero.
- **Largest GEX / largest DEX** — by VOL-based magnitude.

### `hiro.py` (optional output)
Per-trade **signed order flow**, HIRO-style:

```
HIRO_t = Σ s·δ·q·M·F   with aggressor s: B=+1, A=−1, N=0 (from trades.side)
```

Aggregated into `total / calls / puts / zerodte / retail`. Emitted as the
**optional** `hiro` Snapshot field (decision #5, no version bump). Uses
`trades.side` (decision #4) — **no `tbbo` required**.

### `synthetic_oi.py` (optional output — EXPERIMENTAL)
Synthetic-OI #4 positioning lens: an **alternative** GEX basis that anchors on
carried-in open interest and updates it with native aggressor-signed flow.

```
Q(strike) = s_static·OI_open + (−net_aggressor_flow)·w   with s_static long-call/short-put
GEX       = Σ Γ·Q·M·F²·0.01
```

`w ∈ [0, 1]` is tunable (`w=0` = pure OI-GEX / SpotGamma-classic baseline,
`w=1` = full flow update). Thin strikes whose gamma is unsolved upstream are
**skipped, not fabricated**. Reuses the locked dealer signs and `GEX_PCT_SCALE`.
Emitted as the **optional** `synthetic_oi` Snapshot field (additive, no version
bump — follows the `hiro`/`ohlc` precedent), computed only when signed flow is
supplied. **This lives ALONGSIDE the locked VOL-GEX (`exposure.py`) and does NOT
replace it.** It is **EXPERIMENTAL / not price-validated** — structurally checked
on a 4-day sample only. See
[`research/empirical/synthetic-oi-0dte.md`](research/empirical/synthetic-oi-0dte.md).

**Synthetic-OI #6 (size-tiered)** is the same module: `tier_weight(size)` scales
each trade's signed flow by a size tier (retail odd-lots → ~0, institutional blocks
→ >1; per-instrument `BLOCK_MIN_SIZE`, thresholds **UNVALIDATED**) before the worker
sums it into a second flow map. That map drives `build_synthetic_oi` again, emitted
as the optional `synthetic_oi_tiered` field (same `SyntheticOi` shape). With all
tier weights = 1 it reduces exactly to #4.

### `exposure_ext.py` (optional output — EXPERIMENTAL)
Aggregates the higher-order dealer greeks on the **same VOL basis + locked dealer
signs** as `exposure.py`:

```
net_vex  = (sign_c·vanna_c·cvol + sign_p·vanna_p·pvol) · M · F · 0.01    (per 1% IV)
net_chex = (sign_c·charm_c·cvol + sign_p·charm_p·pvol) · M · F · (1/365) (per day)
```

`M·F` dollarises each greek (one `F`, like DEX — vanna/charm differentiate delta
w.r.t. vol/time, not `F`, so there is **no `F²`**). **The two `0.01`s are not the
same physics:** VEX's `0.01` is a **vol-point** scale (per 1% IV), distinct from
GEX's `GEX_PCT_SCALE` (per 1% *price* move) — so VEX is **not** directly
comparable to GEX. CHEX is scaled to **per calendar day** (the 0DTE horizon).
Greeks are re-evaluated from the carried per-leg IV + `t_expiry` (no external tape
needed); **thin strikes are skipped**, never fabricated. Emitted as the optional
`exposure_ext` Snapshot field (additive, no version bump), gated by
`with_exposure_ext` (the worker + session generator pass `True`). **EXPERIMENTAL /
not price-validated.** See
[`research/empirical/track-f-ddoi-exposure-vol.md`](research/empirical/track-f-ddoi-exposure-vol.md).

### `total_hedging.py` (optional output — EXPERIMENTAL)
Synthetic-OI **#7**: applies all three hedging greeks to the **same synthetic
position `Q`** that `synthetic_oi.py` (#4) builds (`Q = s_static·OI + (−flow)·w`),
instead of to VOL:

```
gamma_hedge = Σ Γ·Q·M·F²·0.01          (per 1% price move — == synthetic_oi GEX at w)
charm_hedge = Σ charm·Q·M·F·(1/365)    (per calendar day)
vanna_hedge = Σ vanna·Q·M·F·0.01       (per 1% IV, vol-point)
```

Three **separate** fields — never summed (units differ). Because `Q` already
carries the locked dealer sign (via the shared `synthetic_oi.q_per_leg` helper), the
greeks are weighted by `Q` **directly** — no re-applied sign, unlike the VOL-based
`exposure_ext`. `gamma_hedge` is exactly the #4 synthetic GEX at the same `w` (the
strongest correctness anchor); `charm_hedge`/`vanna_hedge` capture the
afternoon-decay and vol-sensitivity pressure a gamma-only map misses. Thin strikes
skipped. Computed only when signed flow is supplied (same gate as `synthetic_oi`).
**EXPERIMENTAL / not price-validated.** See
[`research/empirical/synthetic-oi-roadmap.md`](research/empirical/synthetic-oi-roadmap.md).

### `surface.py` (optional output — EXPERIMENTAL)
SVI volatility-surface fit + expected-move calculation. `build_surface` fits a
raw-SVI slice to the solved per-leg IVs (OTM side: put below the forward, call
at/above), and summarises it into the optional `surface` Snapshot field: ATM vol,
1-sigma lognormal **expected move** (`F·atm_vol·√T`), ATM skew, fit RMSE, the
no-butterfly flag, and the five raw-SVI params (so a consumer can reconstruct the
whole smile). `None` when fewer than 5 non-thin strikes exist (no fabricated fit).
Gated by `with_surface` (worker + session generator pass `True`). Deterministic
(stdlib Nelder-Mead) and tested, but **not** a price-validated signal —
EXPERIMENTAL.

### `snapshot.py`
The assembler. `build_snapshot(...)` runs the pipeline and returns a validated
`Snapshot`. **Pure and calendar-free** — it receives the resolved
`session_state` and `t_expiry`; it never reads the clock itself. This is what
makes the golden fixture possible: identical inputs → identical Snapshot.

## Determinism & the golden fixture

`tests/golden/snapshot.golden.json` pins a full Snapshot for a known input.
`tests/gen_golden.py` regenerates it. **Only regenerate after an intentional,
reviewed contract/behaviour change** — an accidental golden diff is a red flag.

## Testing

~92 engine tests cover Black-76 vs. references, IV convergence, exposure signs,
field invariants, level extraction, HIRO signing, and the golden snapshot. Run:

```bash
cd services/engine && pytest && ruff check . && mypy
```
