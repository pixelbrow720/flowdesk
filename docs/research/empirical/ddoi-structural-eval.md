# DDOI-GEX vs VOL-GEX — Same-Session Structural Eval (0DTE, exploratory)

> **STATUS: EXPLORATORY mechanism, NOT evidence.** This is a contemporaneous
> (end-of-session) STRUCTURAL-divergence check on the 4 correct 0DTE days. It is
> **not predictive**, **not validated**, and **not in the Snapshot**. It answers one
> narrow question — *is DDOI-GEX structurally different from VOL-GEX, or does it
> collapse to ~±VOL?* — and the first (n=4, descriptive) answer is
> **INCONCLUSIVE, leaning REDUNDANT-with-VOL**. Placed in
> `docs/research/empirical/`, NOT `verified/`.

**Date:** 2026-06-14 · **Instruments:** /ES, /NQ · **Sessions:** Jun 5/8/9/10 2026
(4 days, one a crash arc; 8 session-instruments) · **Data:** the validated
`data/raw/zerodte/` 0DTE pull (gitignored). **Scripts:**
[`/analysis/harness/ddoi_divergence.py`](../../../analysis/harness/ddoi_divergence.py)
(pure core) +
[`/analysis/harness/run_ddoi_divergence.py`](../../../analysis/harness/run_ddoi_divergence.py)
(dbn runner) +
[`/analysis/harness/test_ddoi_divergence.py`](../../../analysis/harness/test_ddoi_divergence.py)
(14 unit tests). Runs **through** the fail-closed tenor-provenance guard
(`assert_session_iids_0dte`).

This is the 0DTE-valid replacement for the WITHDRAWN cross-day head-to-head in
[`track-f-ddoi-exposure-vol.md`](track-f-ddoi-exposure-vol.md) §3 (that "49.2/50.8"
figure was quarterly-data contamination; cross-day ΔOI is structurally impossible on
0DTE). It evaluates DDOI on a **same-session** basis, where an evaluation is even
definable.

---

## 1. The question, and why predictive is out of scope

DDOI drives the locked dealer-sign + gamma GEX template with a per-leg basis
`ddoi_leg = Σ_i w(i)·|size_i|`, time-weighting each leg's trades by the intraday
weight `w(i) = 1 − 2·(i/(n−1))` (+1 first trade of the day → −1 last). The eval asks
whether the resulting per-strike DDOI-GEX profile carries structure the locked
VOL-GEX profile does not.

**Why this is NOT a predictive test (FACT, by construction):** `w(i)` is
**whole-day-normalized** — it needs `n` = the leg's full-session trade count to know
where "late" is. Using it per-minute would peek at the rest of the day, so
per-minute predictive DDOI is **look-ahead-contaminated and explicitly out of
scope** (`ddoi_divergence.py:10-14`, `run_ddoi_divergence.py:10-16`). The eval is
therefore run at **end of session over the whole day's trades, scoring no outcome**
— contemporaneous, so look-ahead-free.

## 2. What `ddoi_leg` actually is: a de-meaned timing-skew statistic

The decisive finding (numeric derivation + read-only 4-day diagnostic, session-
verified by the quant-greeks auditor; corroborated by the red-team):

**The time weight sums to EXACTLY zero** over a leg's trades, `Σ_i w(i) = 0` for
`n ≥ 2` (the lone exception is `n == 1`, w=+1). Because the weights are de-meaned,
`ddoi_leg = Σ w(i)·|size_i|` is **NOT** a contracts-outstanding ΔOI and **NOT** a
volume total — it is the (un-normalized) **covariance of trade `|size|` with
chronological position**, i.e. a **volume timing-skew** statistic:

- `ddoi_leg > 0` ⇒ volume **front-loaded** (bigger trades early),
- `ddoi_leg < 0` ⇒ volume **back-loaded** (bigger trades late),
- `ddoi_leg ≈ 0` ⇒ uniform-in-time.

The "net OPENING / net CLOSING" reading is an **interpretive heuristic label** on
that timing skew, not a measured OI change. (This is now stated in the engine module
docstring too — `services/engine/src/engine/ddoi.py:32-58`, docstring-only
correction; engine tests unaffected.)

**Consequence — the sign-flip artefact.** A back-loaded dominant leg makes
`ddoi_leg` negative on the **same strike** that carries the large VOL, so on those
legs DDOI-GEX ≈ **−c·VOL-GEX**: identical per-strike shape, flipped sign. A raw
signed correlation between DDOI-GEX and VOL-GEX therefore reads strongly **negative**
for a purely **mechanical** reason — not because DDOI found new positioning
structure.

## 3. The upgraded discriminator (separates sign-flip from real re-weighting)

To stop the signed correlation being misread as divergence, `divergence_metrics`
(`ddoi_divergence.py:288-372`) reports, alongside the raw signed `pearson`:

| Metric | What it detects |
|---|---|
| `magnitude_pearson` | Pearson of `\|ddoi\|` vs `\|vol\|` — the **sign-flip detector**. ≈+1 while signed pearson is negative ⇒ same shape, flipped sign ⇒ redundant. |
| `best_fit_scalar_c` + `residual_r2` | least-squares `ddoi ≈ c·vol` and variance explained — the **redundancy detector**. High `\|c\|` + `residual_r2`≈1 ⇒ DDOI is ~a scalar multiple of VOL (no new structure). Only a large structured residual leaves room for genuine divergence. |
| `leg_timing_diagnostic` | per-leg `frac_legs_backloaded`, `mean_late_share` (weight-free), OLS slope of `ddoi_leg ~ vol_leg` — the **mechanical-driver** corroboration. |

The unit tests lock the discriminator with wide margin (`test_ddoi_divergence.py`):
a pure scalar multiple of VOL (sign-flip / redundant) reads `magnitude_pearson`≈+1,
`residual_r2`≈1; a genuine strike reshuffle reads both clearly below 0.9
(`magnitude_pearson`=−0.64, `residual_r2`<0). Two falsification controls run per row:
**uniform-DDOI** (`w≡1`, reduces exactly to VOL — a builder self-check) and
**shuffle-DDOI** (trade time-order randomized).

## 4. Real-data result (4 days, 8 session-instruments — descriptive only)

> These numbers are runtime outputs of `run_ddoi_divergence.py` on the gitignored
> 0DTE pull (session-verified by the quant-greeks auditor + red-team; not
> reproducible from committed files). They are **descriptive over n=4 correlated
> days incl. a crash arc — NOT evidence.**

- Aggregate signed `pearson` ≈ **−0.34**; aggregate `magnitude_pearson` ≈ **0.285**.
- The result is **BIMODAL**: **2/8** rows (NQ Jun-08, NQ Jun-10) are textbook
  sign-flip-redundant (`|magnitude r|` ≈ 0.93–0.98, `residual_r2` ≈ 0.86–0.95); the
  remaining rows are low-magnitude / noise.
- `mean_late_share` ≈ **0.34**, so uniform back-loading is **NOT** cleanly present
  across all 4 days — the back-loading driver is real on some rows, absent on
  others.

So the headline −0.34 is a **heterogeneous mix** of a clean mechanical sign-flip on
a couple of rows plus noise — **not** a uniform structural signal.

## 5. Verdict and what it means

**The gate question — "is DDOI structurally different from VOL, worth funding the
~90-day predictive run?" — is INCONCLUSIVE at n=4, LEANING REDUNDANT-with-VOL.** The
raw −0.34 is largely a `Σw=0` sign-flip artefact of the back-loaded tape plus noise,
not new positioning information.

The auditors explicitly advised **NOT** funding the 90-day predictive build on the
strength of the −0.34. If a 90-day run happens, it should **first** be a structural
disambiguation (magnitude / residual / back-loading), **not** predictive scoring.

This is a **mechanism / structural** result, not signal validation. DDOI stays
EXPERIMENTAL, alongside (never replacing) VOL-GEX, and is not price-validated.

## 6. What this is / isn't

- **Is:** a look-ahead-free, provenance-guarded, unit-tested same-session structural
  comparison that exposes *why* DDOI-GEX correlates negatively with VOL-GEX (the
  de-meaned time weight), with controls that distinguish a sign-flip from genuine
  re-weighting.
- **Isn't:** a predictive test, a validated signal, or a basis to fund the 90-day
  build. 4 correlated days; the open/close split is a heuristic, not ground truth.
- **Deferred (gated on the operator's manual ~90-day anti-lock pull):** a
  properly-powered structural disambiguation on a larger, decorrelated sample.

See also: [`track-f-ddoi-exposure-vol.md`](track-f-ddoi-exposure-vol.md),
[`validation-harness.md`](validation-harness.md),
[`symbology-0dte-findings.md`](symbology-0dte-findings.md).
