# Synthetic-OI #4 FLOW-TERM vs Pure OI-GEX — Same-Session Structural Eval (0DTE, exploratory)

> **STATUS: EXPLORATORY mechanism, NOT evidence.** This is a contemporaneous
> (end-of-session) STRUCTURAL check on the 4 correct 0DTE days. It is **not
> predictive**, **not validated**, and the synthetic-OI family is **absent from the
> committed FE session JSON** (live-worker only). It answers ONE narrow,
> advisor-corrected question — *does synthetic-OI #4's native-aggressor FLOW term add
> per-strike STRUCTURE OVER pure OI-GEX?* — and the n=4 answer for **BOTH /ES and /NQ
> is UNDETERMINED**: the flow term is materially-sized but its DIRECTION is **not
> separable** from random-sign flow of the same magnitude at n=4. Placed in
> `docs/research/empirical/`, NOT `verified/`.

**Date:** 2026-06-14 · **Instruments:** /ES, /NQ · **Sessions:** Jun 5/8/9/10 2026
(4 days, one a crash arc; correlated) · **Data:** the validated
`data/raw/zerodte/` 0DTE pull (gitignored). **Scripts:**
[`/analysis/harness/synthetic_oi_eval.py`](../../../analysis/harness/synthetic_oi_eval.py)
(pure core) +
[`/analysis/harness/run_synthetic_oi_eval.py`](../../../analysis/harness/run_synthetic_oi_eval.py)
(dbn runner) +
[`/analysis/harness/test_synthetic_oi_eval.py`](../../../analysis/harness/test_synthetic_oi_eval.py)
(16 unit tests). Runs **through** the fail-closed tenor-provenance guard
(`assert_session_iids_0dte`). Full harness suite = **74 tests** (16 provenance + 20
metrics + 14 divergence + 8 hiro_eval + 16 synthetic_oi_eval).

This eval covers **only synthetic-OI #4** (`gex` at `w=1` vs `gex_static` at `w=0`).
The #5 decay / #6 tiered / #7 total-hedging variants are **DEFERRED** (§6).

---

## 1. The question — corrected by the-advisor to "flow term OVER pure OI", NOT "vs VOL"

Synthetic-OI #4 per leg is `Q = s_static·OI_open + (−net_aggressor_flow)·w`
(`engine/synthetic_oi.py:139-141`). At `w=0` the additive flow term vanishes and `Q`
is **pure OI-GEX** (SpotGamma-classic); at `w=1` the native-aggressor FLOW term
`(−flow)·w` is fully engaged. The engine only ever emits a SCALAR `synthetic_gex`
summed over strikes (`synthetic_oi.py:167-185`); this eval splits it per-strike and
asks whether the flow term **reshapes** the profile.

**The comparison axis the-advisor corrected (FACT, gating decision):** an earlier
framing compared synthetic-GEX against **VOL-GEX**. That comparison is **CONFOUNDED**
— it mixes the already-decided, LOCKED OI-vs-VOL basis difference (methodology
divergence #1, `docs/reference/methodology-decisions.md`) with the flow term, and is
possibly trivial. The **only** thing synthetic-OI #4 *uniquely* claims over a classic
OI-GEX vendor is the native-aggressor flow update. So the primary arm is
**`gex` (w=1) vs `gex_static` (w=0)**, holding the SAME per-strike gammas and the SAME
`s_static·OI` stock anchor fixed — **NOT** synthetic vs VOL
(`synthetic_oi_eval.py:11-23`, `run_synthetic_oi_eval.py:4-8`).

## 2. Why this is STRUCTURAL, with NO predictive arm and NO 55%

OI on this data is **END-OF-DAY settled only** (`statistics` stat_type 9). The
synthetic-OI stock anchor is `s_static·OI_open` — *prior-session* settled OI. Using
the same-day EOD settle-OI *intraday* would be **look-ahead** (the documented harness
trap), and 0DTE has **zero cross-day symbol overlap** (each day is its own daily
expiry; see [`symbology-0dte-findings.md`](symbology-0dte-findings.md)), so a clean
prior-session `OI_open` may not even exist on disk. A predictive arm (synthetic
gamma-flip → price) is therefore **BLOCKED and out of scope**
(`run_synthetic_oi_eval.py:10-16`).

**Consequence (FACT):** this is an **END-OF-SESSION STRUCTURAL** comparison — nothing
is scored against price, so there is **NO hit-rate / NO "55%"** for this arm. Unlike
the HIRO eval ([`hiro-predictive-eval.md`](hiro-predictive-eval.md), which earned a
predictive test because HIRO is strictly t-causal), synthetic-OI #4's reliance on
settle-OI makes a clean predictive arm undefensible here.

Net-aggressor flow is the whole-day `Σ aggressor_sign·size` since the RTH open — the
same quantity `run_validation.flow_and_vol` accumulates and `engine.synthetic_oi`
consumes (`synthetic_oi_eval.py:124-136`, `run_synthetic_oi_eval.py:154-181`). The
per-strike GAMMA the position model multiplies is read at the **latest late-session
minute whose chain solves** (the 16:00 ET bell is degenerate ⇒ every strike thin), so
the gamma reference is solvable while flow + OI remain whole-day/EOD — still
contemporaneous, look-ahead-free (`run_synthetic_oi_eval.py:262-285`).

## 3. The aggregator anchor — the load-bearing correctness gate

The entire eval rests on a NEW per-strike aggregator, `synthetic_gex_by_strike`
(`synthetic_oi_eval.py:139-171`). It is only trustworthy if it is faithful to the
locked engine. Two locks (FACT — unit-tested, session-verified by the test-author):

- **THE ANCHOR (`test_aggregator_sums_to_engine_scalar`,
  `test_synthetic_oi_eval.py:118-132`):** for every `w ∈ {0.0, 0.5, 1.0}`,
  `sum(synthetic_gex_by_strike(...).values())` equals the engine's scalar
  `engine.synthetic_oi.synthetic_gex(...)` to float tolerance (`math.isclose`,
  `rel_tol=1e-12`). Both reuse the SAME `q_per_leg` `Q`, the SAME
  `M·F²·GEX_PCT_SCALE` scale, and the SAME thin-skip. If this identity broke, the
  per-strike split would be wrong and no downstream metric would mean anything.
- **NO DOUBLE-SIGN (`test_no_double_sign_on_put_heavy_strike`,
  `test_synthetic_oi_eval.py:168-188`):** the dealer sign (`+1` call / `−1` put) is
  ALREADY baked into `Q` at `q_per_leg` (`synthetic_oi.py:139-141`). The documented
  trap is to reuse `ddoi_divergence.gex_by_strike`, which RE-applies `DEALER_SIGN_PUT`
  to its (unsigned) flow map — feeding `Q` into it would **double-sign the puts and
  manufacture fake divergence**. That trap was AVOIDED: `synthetic_gex_by_strike` is a
  NEW sign-free aggregator consuming `q_per_leg` directly and adding no further dealer
  sign. The test pins that the put-heavy strike does NOT match the double-signed value.

Thin strikes (gamma unsolved upstream) are SKIPPED, never fabricated, and the skip is
proven by the anchor surviving an absurd-gamma thin strike
(`test_synthetic_oi_eval.py:135-146`). 16 anchor/metric/shuffle tests pass.

## 4. Metrics + the shuffle control (the DDOI sign-flip detectors deliberately NOT reused)

High similarity between the `w=1` and `w=0` profiles is **EXPECTED** — they share the
same gammas and the same `s_static·OI` anchor; only `(−flow)·w` differs. So the
meaningful quantities are (`flow_term_metrics`, `synthetic_oi_eval.py:232-300`):

| Metric | What it detects |
|---|---|
| `residual_r2` | Variance of the `w=1` profile explained by the scalar fit `gex ≈ c·static`. HIGH (≈1) ⇒ flow is just a **scalar rescale** of OI (no new structure = a null); LOW ⇒ a structured residual ⇒ flow may add per-strike structure. (`_residual_r2` `synthetic_oi_eval.py:204-225`) |
| `flow_norm_ratio` | `‖gex − static‖₂ / ‖static‖₂` — **the headline magnitude**: how big the additive flow term is relative to pure OI. (`synthetic_oi_eval.py:279-281`) |
| `argmax_distance` | `\|argmax(\|gex\|) − argmax(\|static\|)\|` in strike points — does the flow term MOVE the dominant strike? (`synthetic_oi_eval.py:283-287`) |
| **SHUFFLE-FLOW control** | Permute each trade's aggressor SIGN (destroy DIRECTION, preserve magnitude/timing/strike + the global sign multiset), re-net, rebuild the `w=1` profile, compare to the SAME `profile_static`. The real flow term must **beat this same-magnitude random-sign NULL** on `flow_norm_ratio` / `argmax_distance` to carry directional structure. (`shuffle_flow_signs` `synthetic_oi_eval.py:303-327`) |

The headline gap is `norm_ratio_gap` = real `flow_norm_ratio` − mean(shuffle
`flow_norm_ratio`), never the raw norm ratio (`eval_flow_term`
`synthetic_oi_eval.py:357-359`).

**Why the DDOI discriminators were NOT carried (FACT):** `ddoi_divergence`'s
`magnitude_pearson` / `neg_pearson` are sign-flip detectors for DDOI's `Σw=0`
de-meaning artefact ([`ddoi-structural-eval.md`](ddoi-structural-eval.md) §2-3). That
mechanism **cannot occur here** — `w=0` and `w=1` share the same `s_static·OI` anchor,
so there is no de-meaning to flip. The wrong-mechanism detectors are deliberately
omitted (`synthetic_oi_eval.py:174-178`).

## 5. Real-data result (4 days, per-instrument, three-state — descriptive only)

> These numbers are runtime outputs of `run_synthetic_oi_eval.py` on the gitignored
> 0DTE pull (session-verified by the test-author aggregator-anchor + the red-team
> single-day-artefact catch; **not reproducible from committed files**). They are
> **descriptive over n=4 correlated days incl. a crash arc — NOT evidence.**

The aggregate is **PER-INSTRUMENT, never pooled** (the HIRO lesson:
[`hiro-predictive-eval.md`](hiro-predictive-eval.md) §4 — pooling masked the signal),
n-weighted, with a **per-day sign-consistency** gate AND a **single-day-domination**
check before any verdict (`run_synthetic_oi_eval.py:115-151`, `_verdict`
`438-504`). Thresholds are fixed in code and printed at runtime: `residual_r2 ≥ 0.95`
⇒ rescale-null; `flow_norm_ratio < 0.05` ⇒ negligible-null; `norm_ratio_gap ≥ 0.05` ⇒
beats the random-sign null; `MIN_DAYS_FOR_EDGE = 5` (`run_synthetic_oi_eval.py:367-369,
112`).

**/ES — UNDETERMINED.** Per-day `norm_ratio_gap`: {06-05 `−0.017`, 06-08 `−0.025`,
06-09 `+0.171`, 06-10 `−0.010`}; mean **+0.030 < 0.05**; per-day sign **1+/3−
(INCONSISTENT)**. The flow term is materially-sized (mean `flow_norm_ratio` ~0.5) but
its mean gap neither clears the threshold nor is sign-consistent, so its direction is
not separable from random at n=4.

**/NQ — UNDETERMINED (a SINGLE-DAY ARTEFACT, explicitly).** Per-day `norm_ratio_gap`:
{06-05 `+1.017`, 06-08 `+0.277`, 06-09 `−0.401`, 06-10 `−0.479`}; mean **+0.103** —
BUT this rests entirely on **06-05, the thinnest 8-strike profile, whose `+1.017` is
~245% of the 4-day signed sum**. EXCLUDING it the mean is **−0.201 (NEGATIVE)**, and
the per-day sign is **2+/2− (INCONSISTENT)**. The flow term is materially-sized (mean
`flow_norm_ratio` ~0.79), but a positive mean dominated by one high-variance thin-
profile day is not directional structure.

> **NQ was NOT "YES."** A prior verdict mislabeled NQ "YES (exploratory)" off the
> positive mean. The red-team caught it; the verdict logic was then fixed to require
> per-day **sign consistency** AND no single-day domination before "YES" (mirroring
> the HIRO consistency gate), so NQ now correctly reads **UNDETERMINED** and can
> NEVER read YES on this data (`run_synthetic_oi_eval.py:455-473`). See §7.

**HEADLINE (derived, do NOT strengthen): the flow term is MATERIALLY-SIZED (norm
ratio ~0.5 /ES, ~0.79 /NQ) but its DIRECTION is NOT separable from random-sign flow of
the same magnitude at n=4** — real beats the shuffle null by only ~+0.03 (/ES) or
~+0.10-but-single-day (/NQ). This is **NOT a demonstrated structural edge, and NOT a
demonstrated absence.**

## 6. Limits + what is DEFERRED (explicit)

- **n = 4 correlated days**, one a crash arc — far too small; the `MIN_DAYS_FOR_EDGE =
  5` gate exists precisely so no consistent gap could be upgraded to "YES" here.
- **Thin profiles dominate variance.** NQ 06-05 is an 8-strike profile and single-
  handedly swings the NQ mean; ES profiles are also small. A magnitude-mean over so
  few thin profiles is fragile.
- **EOD-settle-OI is the stock anchor**, not prior-session `OI_open`; intraday OI
  would be look-ahead (§2). The `s_static` OI direction is the same irreducible
  assumption every vendor makes; `w` is a HEURISTIC knob, not ground truth.
- **DEFERRED — #5 decay / #6 tiered:** the offline harness builds **one** flow map;
  the tiered/decayed maps exist only in the live worker (`worker.py:394-397`). A new
  tier/decay flow-map construction is needed to evaluate them.
- **DEFERRED — #7 total_hedging:** its `gamma_hedge` equals #4 `gex` bit-for-bit
  (`total_hedging.py:17,62`) — already covered here. Only `charm_hedge` /
  `vanna_hedge` are novel and remain unevaluated.
- **DEFERRED — FE wiring:** the synthetic-OI family is **absent from the committed FE
  session JSON** (the offline generator `gen_session_snapshots.py` passes no
  `net_flow*`); it renders only off a live worker. See
  [`../../08-status-and-gaps.md`](../../08-status-and-gaps.md) gap #2.

## 7. The verdict-logic bug found + fixed (a repeat of the HIRO pooling defect class)

A defect was found in the runner and fixed: the verdict had **no per-day
sign-consistency gate**, so a positive magnitude-mean dominated by one high-variance
thin-profile day (NQ 06-05) could read "YES (exploratory)" even though the per-day
signs were a coin-flip. This is the **same defect CLASS** as the earlier HIRO
ES+NQ-pooling defect ([`hiro-predictive-eval.md`](hiro-predictive-eval.md) §4). The
fix adds the per-day sign tally + single-day-domination check
(`_gap_sign_tally` `run_synthetic_oi_eval.py:115-151`) and routes any
sign-inconsistent or single-day-dominated instrument to UNDETERMINED, NEVER YES
(`run_synthetic_oi_eval.py:455-473`). The structural lesson: **a magnitude-mean
dominated by one thin-profile day must never override a coin-flip per-day sign.**

## 8. Verdict and what it means

**The question — "does synthetic-OI #4's native-aggressor flow term add per-strike
STRUCTURE over pure OI-GEX?" — is UNDETERMINED for BOTH /ES and /NQ at n=4.** The flow
term is materially-sized (it is not negligible vs pure OI), but its DIRECTION is not
separable from a same-magnitude random-sign null on this sample. This is **not a
demonstrated edge, and not a demonstrated absence.**

This is a **mechanism / structural** result, not signal validation. Synthetic-OI
stays EXPERIMENTAL, lives alongside (never replacing) the locked VOL-GEX, and is **not
price-validated**. The reverse-engineered SpotGamma-style framing (`w`, `s_static` OI
direction) is an INFERRED approximation, not official numbers.

## 9. What this is / isn't

- **Is:** a look-ahead-free (EOD-structural), provenance-guarded, unit-tested,
  aggregator-anchored (`sum == engine scalar`, no double-sign) same-session comparison
  of the flow term vs pure OI-GEX, with a shuffle-flow null and a per-day
  sign-consistency + single-day-domination gate.
- **Isn't:** a predictive test, a hit-rate / "55%" (no predictive arm — settle-OI
  intraday is look-ahead), a validated signal, or a "vs VOL" comparison (that axis is
  confounded — §1). 4 correlated days; thin profiles; EOD-settle-OI anchor.
- **Deferred:** #5 decay / #6 tiered (need new flow-map construction), #7
  `charm_hedge` / `vanna_hedge`, and the FE wiring (synthetic-OI absent from committed
  session JSON). A properly-powered, decorrelated sample would be required to resolve
  edge-vs-null — and is not in scope.

See also: [`hiro-predictive-eval.md`](hiro-predictive-eval.md),
[`ddoi-structural-eval.md`](ddoi-structural-eval.md),
[`synthetic-oi-0dte.md`](synthetic-oi-0dte.md),
[`synthetic-oi-roadmap.md`](synthetic-oi-roadmap.md),
[`validation-harness.md`](validation-harness.md).
