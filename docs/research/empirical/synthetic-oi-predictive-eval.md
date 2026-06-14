# Synthetic-OI t→t+k Predictive Eval — VOLATILITY-REGIME, Look-Ahead-Free (0DTE, exploratory)

> **STATUS: EXPLORATORY mechanism, NOT evidence.** This is a CONTROLLED,
> t-causal, look-ahead-free predictive check of synthetic-OI as a **VOLATILITY-
> REGIME** predictor (NOT a directional one) on the 0DTE days on disk. It is **not
> validated**, **not in the Snapshot**, and answers one narrow question — *do
> SHORT-gamma minutes (sign of net synthetic-GEX < 0) show LARGER subsequent
> forward moves than LONG-gamma minutes, BEYOND the regime-label-shuffle /
> aggressor-sign-shuffle / flow-only controls?* The honest answer at **n=3 usable
> days** is **UNDETERMINED — NOT shown, and NOT refuted** (every cell is
> sign-inconsistent or single-day-dominated, and the `MIN_DAYS_FOR_EDGE = 5` gate
> makes a YES unreachable). Placed in `docs/research/empirical/`, NOT `verified/`.

**Date:** 2026-06-14 · **Instruments:** /ES, /NQ · **Usable sessions:** Jun 5/9/10
2026 (**3 days**; Jun 8 DROPPED — no pre-open OI anchor, §5) · **Data:** the
validated `data/raw/zerodte/` 0DTE pull + `data/raw/_probe/` (gitignored).
**Scripts:**
[`/analysis/harness/synthetic_oi_regime_eval.py`](../../../analysis/harness/synthetic_oi_regime_eval.py)
(pure core) +
[`/analysis/harness/run_synthetic_oi_regime_eval.py`](../../../analysis/harness/run_synthetic_oi_regime_eval.py)
(dbn runner) +
[`test_synthetic_oi_regime_eval.py`](../../../analysis/harness/test_synthetic_oi_regime_eval.py)
+
[`test_synthetic_oi_regime_runner.py`](../../../analysis/harness/test_synthetic_oi_regime_runner.py)
(2 test files). Runs **through** the fail-closed tenor-provenance guard
(`assert_session_iids_0dte`, `run_synthetic_oi_regime_eval.py:351`). Full harness
suite = **109 tests pass**.

This is the **second** experimental lens to earn a *predictive* test, after
[`hiro-predictive-eval.md`](hiro-predictive-eval.md). It realizes the user's
"simulate live from historical" idea: there is **no real-time OI feed** (exchanges
publish OI once daily at settle — that is the whole reason synthetic-OI exists), so
the predictor must be reconstructed from a prior-session OI anchor + intraday
signed flow. That reconstruction is **t-causal** and the eval is therefore
**RUNNABLE look-ahead-free on existing data** — it is **UNDERPOWERED (n=3), not
blocked.** Nothing graduates from "mechanism" to "evidence" here; the only blocker
to a real verdict is statistical power (more days), which needs a data pull the
user dropped.

---

## 1. The question — REGIME, not direction (and why)

Synthetic-OI/GEX is, by the advisor's standing constraint, a **volatility-regime**
indicator, not a price-direction one. The sign of net dealer gamma sets the dealer
hedging posture:

```
regime_t = sign( Σ synthetic-GEX_t )            (synthetic_oi_regime_eval.py:79-94)
  +1  LONG-gamma   ⇒ dealers SUPPRESS vol (sell rallies / buy dips) ⇒ SMALL moves
  -1  SHORT-gamma  ⇒ dealers AMPLIFY  vol (chase the move)          ⇒ LARGE moves
   0  flat/empty   ⇒ UNSCORED (no regime call this minute)
```

So the **outcome is a SIGN-FREE realized move magnitude** `|F_{t+k} − F_t|`
(`realized_move`, `synthetic_oi_regime_eval.py:117-128`), **NOT a signed return** —
direction is explicitly not claimed. The core metric is the regime SEPARATION
(`regime_separation`, `:139-208`):

```
sep_k = ( mean(move | short-gamma) − mean(move | long-gamma) ) / mean(move | all scored)
```

`sep > 0` is the hypothesised ordering (short-gamma minutes move MORE). `mean_all`
normalises out the day's overall volatility level so `sep` is comparable across
days. **This deliberately does NOT reuse the HIRO directional kernel**
(`sign(delta) → sign(return)`): a flow-only directional arm would ~duplicate the
already-null HIRO eval, and the new, distinct content here is the **prior-OI-
anchored vol-regime predictor**. The predictor itself is
`Q = prior-session-OI-anchor + cumulative_signed_flow(≤ t)` — the same t-causal
positioning quantity `engine.synthetic_oi.q_per_leg` consumes
(`synthetic_oi.py:139-141`), fed into the sign-free `synthetic_gex_by_strike`
aggregator (`run_synthetic_oi_regime_eval.py:323`); only its SIGN enters the metric.

## 2. Why a RAW separation is meaningless — the control GAP is the headline

A day with any persistent volatility clustering can produce a non-zero `sep` even
if the regime label carries no information (quiet minutes happen to cluster). So
the headline is never the raw `sep`; it is the **gap against controls**. Three
nulls are reported per `k`:

| Control | What it isolates | Code |
|---|---|---|
| **Regime-label shuffle** (HEADLINE) | Permute the regime labels; the move series and the per-day long/short/flat counts are preserved, but the ALIGNMENT between which minutes are long/short and which minutes moved is destroyed. `sep_real − mean(sep \| shuffled-labels)` is the edge SPECIFICALLY from the regime labelling, not from clustering. | `shuffle_regimes`/`headline_gap` `synthetic_oi_regime_eval.py:214-286` |
| **Aggressor-sign shuffle** | Rebuild regimes from sign-permuted flow (SAME OI anchor, SAME solved gammas, same sign multiset) — does the real flow DIRECTION matter, or would random-direction flow of the same magnitude separate moves equally? | `run_synthetic_oi_regime_eval.py:434-441, 452-462` |
| **Flow-only (anchor = 0)** | Re-run with the prior-session OI stock zeroed (same gammas) so the regime is driven by `(−flow)·w` alone — isolates whether the FLOW or the OI STOCK carries any separation. | `run_synthetic_oi_regime_eval.py:408, 425, 466` |

The headline quantity is `headline_gap = sep_real − mean(sep | regime-label
shuffle)` (`synthetic_oi_regime_eval.py:240-286`); the verdict is DERIVED from the
per-day headline-gap tally, never hardcoded (`run_synthetic_oi_regime_eval.py:602-624`).

## 3. The t-causal OI anchor — the load-bearing look-ahead-free argument

The whole predictive legitimacy rests on the anchor being observed **before** the
session opens. `_preopen_oi_anchor` (`run_synthetic_oi_regime_eval.py:134-204`)
takes, per `instrument_id`, the `stat_type == 9` (open-interest) **`quantity`**
(not `price` — that field is the `INT64_MAX` sentinel on stat9 OI rows) from the
record with the **MAXIMUM `ts_recv` SUBJECT TO `ts_recv < RTH_open`** (09:30 ET =
13:30 UTC on these June/EDT dates; the hard guard is `:169-170`).

**Why the predicate is hard and NEVER relaxed (FACT):** CME republishes the SAME
prior-session OI *intraday* (~14:1x UTC) carrying the SAME `ts_ref` as the genuine
pre-open snapshot, so **only `ts_recv < open` distinguishes the look-ahead-free
anchor from the intraday republish** (`:144-148`, `:26-30`). A day whose only stat9
is the intraday republish gets an EMPTY anchor and is **DROPPED**, never salvaged by
widening the predicate (`:368-373`).

**Provenance, fail-closed (FACT, flagged not silently changed):** the build spec
assumed the chosen record's `ts_ref` ET-date is `D-1`. On the real on-disk data it
is the *lagged prior settlement session* (D-2 / prior business session:
06-05→06-03, 06-09→06-07, 06-10→06-08) because CME's reported OI reference date
trails by a settlement cycle. A literal `== D-1` raise would false-reject every
usable day, so the enforced invariant is the meaningful one: the anchor's `ts_ref`
ET-date **must be a PRIOR session (`< session_date`)**; a same-day-or-future
`ts_ref` is itself a leak signal and **RAISES** (`:184-197`). This deviation is
documented inline (`:32-42`) and the actual `ts_ref` + day-gap is printed for every
used day, rather than being hidden.

The predictor/outcome split: the regime PREDICTOR at minute `t` uses the anchor +
flow accumulated `< grid_secs[t]` (`= open + t·60`, the exact timestamp of the
parity forward `F_t`); the OUTCOME `|F_{t+k} − F_t|` is realized strictly later
(`> t`). **The two information sets never overlap — look-ahead-free by
construction.**

## 4. Red-team found a residual leak — found, fixed, and LOCKED

The red-team caught **one residual look-ahead** in the cumulative-flow series: the
snapshot for minute `t` originally folded in minute-`t`'s own trades *before*
snapshotting, so `out[t]` carried trades that printed AT-OR-AFTER `F_t`'s instant —
contemporaneous flow shared with the outcome.

**Fix (snapshot-before-fold):** `_cum_netflow_series`
(`run_synthetic_oi_regime_eval.py:269-306`) now snapshots the running net-flow at
the START-of-minute-`t` boundary `grid_secs[t]` **before** folding minute `t`'s own
trades (`:301-302`). So `out[t]` includes ONLY trades with `ts < grid_secs[t]`
(cumulative through the END of minute `t−1`), and the first scored minute `t=0` is
**anchor-only** (`out[0] == {}` ⇒ flow = 0), handled cleanly downstream by
`q_per_leg`'s `net_flow.get(..., 0.0)`.

**Two things make the fix trustworthy:**
- **The null held UNCHANGED after the fix.** The leak was *masked* at this n (it did
  not manufacture a false signal); removing it did not move the verdict — which is
  exactly what a benign, correctly-detected leak should do at n=3.
- **The anti-leak guarantee is now an explicit test contract.** Two runner tests
  encode `out[0] == {}` and assert the OLD leaky value first surfaces at `out[1]`,
  not `out[0]` (`test_synthetic_oi_regime_runner.py:352`, `:378`) — so a regression
  to the leaky fold FAILS the suite.

## 5. Hard limits (explicit — these are the whole reason the verdict is UNDETERMINED)

- **Only 4 0DTE days exist on disk, and Jun 8 is DROPPED → n = 3 usable.** Jun 8
  publishes NO pre-open OI (its only stat9 is the ~14:11 UTC intraday republish), so
  using it would be look-ahead; it is dropped per the §3 predicate
  (`run_synthetic_oi_regime_eval.py:44`, `:368-373`). The 3 usable days
  (06-05/06-09/06-10) are correlated — far too few for an edge claim; the
  `MIN_DAYS_FOR_EDGE = 5` gate (`:127`) exists precisely so a consistent result here
  cannot be upgraded to EDGE.
- **/ES is gamma-dense, /NQ is sparse.** Decoded/session-verified solvable-minute
  counts: ES ~360–379 solvable directional minutes per day, NQ ~103–171. NQ days can
  fall below the `MIN_SCORED_MINUTES = 20` directional-minute floor and are then
  reported as `sparse → UNDETERMINED`, never faked (`:130-131`, `:490-491`).
- **06-05 has NO regime flip (all short-gamma) → zero within-day separation.** With
  no long-gamma minutes the short-vs-long contrast is undefined; the runner reports
  `no-regime-variation` and that day contributes ZERO separation, reported not faked
  (`:492-493`, `:564-567`; degenerate-arm handling `regime_separation`
  `synthetic_oi_regime_eval.py:182-194`).
- **The forward is an OPTION-DERIVED put-call-parity forward, NOT a traded futures
  price** — reused VERBATIM from the HIRO runner's `build_minute_forwards`
  (`run_synthetic_oi_regime_eval.py:82-86, 380-382`). There are no futures
  trades/bbo on disk; "price" here is a parity reconstruction, not /ES itself.
- **Only `k ∈ {5, 15, 30}` minutes were tested** (`K_SET`, reused from the HIRO
  runner). Sub-minute and horizons > 30 min are unmeasured (NEEDS-VERIFICATION — not
  claimed either way).

## 6. The harness is ALIVE — the load-bearing positive control

A null is only trustworthy if the metric can be PROVEN to detect a signal when one
exists. The positive control (`test_synthetic_oi_regime_eval.py:52`, FACT —
unit-tested): plant a regime/move alignment where short-gamma minutes move strictly
more than long-gamma minutes → `headline_gap` is positive; the anti-control
(flipped planting, `:89`) → the gap goes negative. The metric reaches both signs on
planted data, so it is **ALIVE** — the real-data UNDETERMINED is a genuine
"cannot resolve at this n", not a dead-metric artefact. Degenerate-arm semantics
(all-long, all-short, mean_all = 0, no scored minutes) each return `sep = None` with
a human-readable reason (`:127-164`), so empty arms are explicit, never a fake zero.

## 7. Real-data result (3 usable days, per-instrument — descriptive only)

> These are runtime outputs of `run_synthetic_oi_regime_eval.py` on the gitignored
> 0DTE pull (decoded / session-verified; **not reproducible from committed files**).
> They are **descriptive over n=3 correlated days — NOT evidence.**

Aggregation is **per-instrument, never pooled** (the same defect class the HIRO and
synthetic-OI structural evals were both bitten by), and the verdict is a derived
three-state classifier that requires (a) a defined headline gap, (b) per-day sign
consistency, (c) no single-day domination, and (d) `n_days ≥ MIN_DAYS_FOR_EDGE`
before it will say EDGE (`run_synthetic_oi_regime_eval.py:602-624`):

- **/ES — UNDETERMINED at every `k ∈ {5,15,30}`.** The per-day headline-gap sign is
  inconsistent across the usable days (and 06-05 contributes zero separation as a
  no-flip day), so the result reads as coin-flip / single-day-dominated, never a
  consistent directional gap. UNDETERMINED, not refuted.
- **/NQ — UNDETERMINED at every `k`.** NQ is sparse (§5): days fall below the
  directional-minute floor or are single-day-dominated, so no `k` resolves
  edge-vs-null.

**HEADLINE (derived, do NOT strengthen): UNDETERMINED — synthetic-OI's vol-regime
predictive power is NEITHER shown NOR refuted at n=3.** This is the honest expected
outcome at this n; the eval is correct, look-ahead-free, and reusable. A YES is
unreachable by construction below `MIN_DAYS_FOR_EDGE = 5`.

### On any "hit-rate" / target framing

There is no hit-rate and no "55%" here. The only meaningful quantity is the control
gap, and it does not resolve at n=3. No threshold was tuned to hit a target;
`MIN_DAYS_FOR_EDGE`, `MIN_SCORED_MINUTES`, and the shuffle seeds are fixed in the
code and printed at runtime (`:73`, `:127`, `:131`).

## 8. Verdict and what it means

**UNDETERMINED at n=3 — NOT shown, NOT refuted.** Both instruments are
sign-inconsistent or single-day-dominated at every horizon; the gate keeps
"underpowered" from collapsing into either "edge" or "no edge". This is a
**mechanism** result, not signal validation. Synthetic-OI stays EXPERIMENTAL, lives
alongside (never replacing) the locked VOL-GEX, and is **not price-validated**.

The single blocker to a real verdict is **statistical power** — more independent
0DTE days. The method is sound: t-causal, look-ahead-free (anchor predicate +
snapshot-before-fold), control-anchored, positive-control-proven-alive, and the
harness is a **reusable template** the moment a properly-powered, decorrelated pull
with a real futures price exists. The user **dropped that data pull**, so this stays
exploratory and nothing is promoted.

## 9. What this is / isn't

- **Is:** a t-causal, look-ahead-free (pre-open OI anchor with a never-relaxed
  `ts_recv < open` predicate + fail-closed `ts_ref`-prior-session provenance +
  snapshot-before-fold cumulative flow), provenance-guarded, control-anchored,
  positive-control-proven-alive **predictive probe of synthetic-OI as a
  VOLATILITY-REGIME predictor**, with a per-instrument three-state classifier that
  keeps "underpowered" separate from "null".
- **Isn't:** a validated signal, a futures-price backtest, a directional predictor,
  or a basis to claim synthetic-OI predicts /ES volatility. 3 correlated usable days;
  the forward is a parity reconstruction; NQ is sparse; 06-05 has no regime flip; the
  k-set is narrow.
- **Deferred (the user dropped it):** a properly-powered, decorrelated forward run
  with a traded futures price, plus sub-minute and longer-horizon leads. Until then
  the verdict stays UNDETERMINED.

See also: [`hiro-predictive-eval.md`](hiro-predictive-eval.md),
[`synthetic-oi-eval.md`](synthetic-oi-eval.md),
[`ddoi-structural-eval.md`](ddoi-structural-eval.md),
[`validation-harness.md`](validation-harness.md).
