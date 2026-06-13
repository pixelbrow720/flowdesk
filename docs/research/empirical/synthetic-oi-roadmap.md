# Synthetic-OI Roadmap — Formulas #5 / #6 / #7 (PLAN, not built)

> **STATUS: PLAN ONLY.** Nothing here is implemented. This is the buildable spec
> for the three synthetic-OI successors named in
> [`synthetic-oi-0dte.md`](synthetic-oi-0dte.md) §roadmap, turned into concrete,
> data-checked specifications. Every formula, decay constant, size threshold, and
> field shape below is a **proposal flagged as such** — the research doc supplies
> only one-line intents for #5/#6 and a greek list for #7. **No formula here is
> price-validated**; all would ship EXPERIMENTAL like #4.

**Date:** 2026-06-13 · **Template:** `engine/synthetic_oi.py` (#4, built) ·
**Discipline (non-negotiable, inherited from #4):** additive **optional** Snapshot
field, `None` when the signed tape is absent (mirrors `hiro`/`ohlc`/`synthetic_oi`)
→ **no `schema_version` bump**; lockstep mirror `schema.py` ↔ `snapshot.ts` ↔
`CONTRACT.md` (run contract-guardian); **skip thin strikes** (never fabricate
greeks); validated **structurally only**; lives **alongside** the locked VOL-GEX,
never replaces it.

---

## 0. The shared refactor these depend on

#4's engine consumes a **pre-summed** map `net_flow: Mapping[(strike, is_call), float]`
(`synthetic_oi.py:79`), built by `worker._net_flow_for` which collapses
`Σ aggressor_sign·size` per leg. That sum **destroys per-trade time and size** — so
**#5 and #6 cannot use it**. They need the **per-trade tape**.

- `get_hiro_trades` (`feed/historical.py:229`) already yields `(event, HiroTrade)`
  pairs with the timestamp paired in, but `HiroTrade` (`hiro.py:91`) stores only
  `price/size/side` — **no `ts` field**. So the timestamp exists at the boundary and
  is dropped one layer too early.
- **Refactor (do once, in #6):** add an optional per-trade overload to the synthetic
  engine that takes the raw signed tape instead of the summed map. #4 keeps its
  summed-map path unchanged (additive). #5 also needs `HiroTrade.ts` added (or the
  tape passed as `(ts, HiroTrade)` tuples, which `get_hiro_trades` already produces).

**Sequencing: #7 → #6 → #5** (lowest risk / highest reuse first).

---

## 1. #7 — Total-hedging map (BUILD FIRST)

**Idea (doc `synthetic-oi-0dte.md` §roadmap):** dealer hedging for 0DTE is not
gamma-only — **charm** (delta decay, explodes into the 16:00 bell) and **vanna**
(delta-vs-vol) matter. A gamma-only map understates afternoon pressure.

**Spec — three SEPARATE fields, not a blended scalar** (units differ; summing them
is dimensionally invalid):
```
gamma_term(Q) = Σ Γ·Q·M·F²·0.01          # = current #4 synthetic GEX (per 1% move)
charm_term(Q) = Σ charm·Q·M·F·(1/365)     # per calendar day
vanna_term(Q) = Σ vanna·Q·M·F·0.01        # per 1% IV (vol-point)
```
where `Q` = #4's synthetic position (`s_static·OI_open + (−net_flow)·w`).

**This is VEX/CHEX on the synthetic-OI base.** It reuses *exactly* the scaling
already shipped and red-team-resolved in `engine/exposure_ext.py` (commit `0a5cec1`)
— the only change is substituting `Q` for `VOL`. The CHEX 80–470× open→close build
(`track-f-ddoi-exposure-vol.md`) is the mechanism #7 captures that #4 misses.

**Data/feasibility:** ZERO new market data. `ChainRow` already carries
`call_iv/put_iv/t_expiry` (`exposure.py:117-119`); vanna/charm are FD-validated
(`black76.py:270,293`). Only API change: thread `rate` into the synthetic engine
(it currently doesn't take it; the call site has it).
**Risk:** lowest. Mechanical reuse of validated primitives.

## 2. #6 — Size-tiered classification (BUILD SECOND)

**Idea:** large trades = institutional/dealer-relevant; small odd-lots = retail
noise. Weight flow by a size tier before summing.

**Spec (PROPOSED — thresholds are guesses, must be swept):**
```
Q6 = s_static·OI_open + w · Σ_i (−a_i)·size_i·g(size_i)
g(size) = tiered weight: {size ≤ θ_lo → ~0 (retail), θ_lo<size<θ_hi → 1, size ≥ θ_hi → >1 (block)}
```
- `θ_lo`: reuse `RETAIL_MAX_SIZE = 5.0` (`hiro.py:69`) as the retail cutoff.
- `θ_hi` (block): **starting guess** /ES ≈ 50, /NQ ≈ 25 contracts — **NOT validated.**
  Requires a size-distribution study on the 0DTE tape first; do **not** hardcode
  tiers without it.
- Strict-generalization: `g ≡ 1` ⇒ reduces exactly to #4.

**Data/feasibility:** `size` is fully available (`HiroTrade.size`). Needs the
per-trade-tape refactor (§0) because `_net_flow_for` pre-sums size away. No new feed
capability. **Risk:** medium — thresholds are unvalidated knobs; establishes the
refactor #5 reuses.

## 3. #5 — Decay-weighted flow (BUILD LAST)

**Idea:** recent flow should outweigh old flow (mitigates intraday round-trip
double-count — a buy then sell of the same lot should net toward zero as both age).

**Spec (PROPOSED — λ is an unobservable knob, like `w`):**
```
Q5(t) = s_static·OI_open + w · Σ_{i: t_i≤t} (−a_i)·size_i·exp(−λ·(t − t_i))
λ = ln2 / H,  H = half-life in minutes (sweep e.g. {15, 30, 60, ∞})
```
- Strict-generalization: `H → ∞` ⇒ `exp(·)=1` ⇒ reduces exactly to #4.
- Directly attacks the round-trip confound flagged by Lapis-1
  (`lapis1-doi-reconciliation.md`: direction not recovered, mechanism = open/close
  ambiguity).

**Data/feasibility:** needs per-trade `ts` (drop fixed in §0: add `HiroTrade.ts` or
consume the `(ts, HiroTrade)` tape `get_hiro_trades` already emits) **and** an
evaluation time `t`. **Risk:** highest — most moving parts, and `H`/`λ` is as
unobservable as `w` (an explicit model assumption, not data).

---

## 4. Cross-cutting honesty notes

- **`w` and `λ` and the size tiers are model assumptions, not data.** The open/close
  split is unobservable from the tape (`synthetic_oi-0dte.md`); every knob here
  multiplies that irreducible assumption. Ship each with a sweep, not a single
  blessed value.
- **NQ is fragile** (thin/partial OI anchor) — the same caveat as #4 applies; expect
  noisier NQ results across all three.
- **Validation path:** each formula plugs into the harness (`analysis/harness/`,
  [`validation-harness.md`](validation-harness.md)) so the operator's ~90-day forward
  run ranks them on the same footing as #4 (`w=0/0.5/1`). The strict-generalization
  property (`H→∞`, `tiers≡1` ⇒ #4) makes each a measurable **superset** of #4, so
  the forward test can isolate whether the added complexity earns its keep.
- **#8 (Kalman latent-inventory)** is explicitly out of scope — "heavy; future".

## 5. One-line recommendation

Build **#7 first** (pure reuse of the just-shipped VEX/CHEX machinery on the `Q`
base, zero new data, lowest risk), then **#6** (establishes the per-trade-tape
refactor), then **#5** (reuses the refactor + adds the timestamp + decay knob). None
before the harness has a forward dataset to rank them on — otherwise we add three
unvalidated knobs to a paid product with no way to tell if any helps.
