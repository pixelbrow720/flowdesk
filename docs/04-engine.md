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
   ├─ surface.py    SVI fit + expected move (ISOLATED — not yet in Snapshot)
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

### `surface.py` (ISOLATED — built, not wired)
SVI volatility-surface fit + expected-move calculation. Complete and tested but
**not part of the Snapshot** and not consumed anywhere yet. Wiring it in (plus
VEX/CHEX from vanna/charm) is a roadmap item.

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
