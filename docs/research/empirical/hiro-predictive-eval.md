# HIRO t→t+k Predictive Eval — Controlled, Look-Ahead-Free (0DTE, exploratory)

> **STATUS: EXPLORATORY mechanism, NOT evidence.** This is a CONTROLLED,
> look-ahead-free predictive check of HIRO on the 4 correct 0DTE days. It is
> **not validated**, **not in the Snapshot**, and answers one narrow question —
> *does the SIGN of per-minute HIRO flow lead the SIGN of the future forward return,
> BEYOND the sign-shuffled / signed-volume / contemporaneous / persistence
> controls?* The honest answer at n=4 is **NOT a demonstrated edge, and NOT a
> demonstrated absence** (k=15/30 read NULL on adequate-coverage ES; k=5 ES is a
> small, AT-THRESHOLD, UNDERPOWERED hint; k=5 NQ is UNDETERMINED on coverage).
> Placed in `docs/research/empirical/`, NOT `verified/`.

**Date:** 2026-06-14 · **Instruments:** /ES, /NQ · **Sessions:** Jun 5/8/9/10 2026
(4 days, one a crash arc; correlated) · **Data:** the validated
`data/raw/zerodte/` 0DTE pull (gitignored). **Scripts:**
[`/analysis/harness/hiro_eval.py`](../../../analysis/harness/hiro_eval.py)
(pure core) +
[`/analysis/harness/run_hiro_eval.py`](../../../analysis/harness/run_hiro_eval.py)
(dbn runner) +
[`/analysis/harness/test_hiro_eval.py`](../../../analysis/harness/test_hiro_eval.py)
(8 unit tests). Runs **through** the fail-closed tenor-provenance guard
(`assert_session_iids_0dte`).

This is the **one** experimental lens that earns a *predictive* test. The DDOI
eval ([`ddoi-structural-eval.md`](ddoi-structural-eval.md)) was forced to be
contemporaneous-only because its time weight is look-ahead-contaminated
per-minute; HIRO has no such contamination (§1). Even so, the result here stays
exploratory — the user dropped the ~90-day forward run, so nothing graduates from
"mechanism" to "evidence".

---

## 1. The question, and why HIRO (unlike DDOI) earns a predictive test

HIRO is, by construction, **strictly t-causal** — the per-minute cumulative
delta-notional is

```
HIRO_t = Σ_{trade k ≤ t}  sign(aggressor_k) · δ_k · size_k · M · F_k
```

so a trade contributes only to minutes at-or-after the minute it printed in, and
the per-minute increment `delta_hiro_t` depends ONLY on trades that arrived in
minute `t`, priced at minute `t`'s frozen forward (`hiro_eval.py:9-23`,
`per_minute_hiro` `hiro_eval.py:108-190`). Scoring the SIGN of `delta_hiro_t`
against the SIGN of the FUTURE forward return `F_{t+k} − F_t` therefore uses a
predictor known by the close of minute `t` and an outcome realized strictly later
at `t+k`. **The two information sets never overlap — look-ahead-free by
construction** (the split is enforced in `lead_lag_sign_agreement`: predictor uses
`≤ t`, outcome `> t`; `hiro_eval.py:299-314`). A behavioural look-ahead lock test
mutates only the FUTURE forwards and asserts the past deltas are byte-for-byte
unchanged (`test_hiro_eval.py:177-198`).

**Why this is legitimate for HIRO but was NOT for DDOI (FACT):** DDOI's time
weight `w(i) = 1 − 2·(i/(n−1))` is whole-day-normalized — it needs `n` = the leg's
full-session trade count to know where "late" is, so per-minute predictive use
would peek at the rest of the day (`ddoi-structural-eval.md` §1). HIRO carries no
such normalization, so the per-minute increment is genuinely causal. This is the
one structural reason HIRO can be scored forward and DDOI cannot.

## 2. Why a RAW hit-rate is meaningless — the control GAP is the headline

A coin-flip predictor scores ~0.5, but pure momentum/persistence on a trending
0DTE session can push a naive hit-rate well above 0.5 with NO information in the
predictor. So the headline is never the raw hit-rate; it is the **gap against
controls** (`hiro_eval.py:26-44`, `eval_controls` `hiro_eval.py:362-454`):

| Control | What it isolates |
|---|---|
| **Shuffled-sign** | Same sizes/greeks/timing, aggressor signs permuted (direction destroyed); the day's sign multiset is preserved. `real − mean(shuffle)` is the directional edge over a predictor with HIRO's magnitude but no real direction. The **primary headline gap**. (`shuffle_signs` `hiro_eval.py:337-356`) |
| **Signed-volume** (no greek) | `Σ sign·size` — does the Black-76 δ weighting add anything over plain signed order flow? (`signed_volume_series` `hiro_eval.py:196-243`) |
| **Contemporaneous** | `delta_hiro_t` vs the PAST return `F_t − F_{t−k}`; if HIRO merely *reflects* the move that already happened, this scores high while the predictive arm does not. `predictive − contemporaneous` isolates lead from lag. (`hiro_eval.py:317-331`) |
| **Persistence floor** | `sign(F_{t−k}→F_t)` vs the future return — the pure momentum baseline a real predictor must beat. (`hiro_eval.py:412-415`) |

The decisive rule, stated in the code and printed at runtime: **a raw ~0.55
hit-rate is meaningless if the shuffled control also reaches it.** The two headline
quantities are `real_minus_shuffle` and `predictive_minus_contemp`
(`hiro_eval.py:382-385`, `447-448`); the verdict line is DERIVED from them, never
hardcoded (`run_hiro_eval.py:489-500`).

## 3. The harness is ALIVE — the load-bearing positive control

A null is only trustworthy if the metric can be PROVEN to detect a signal when one
exists; a metric stuck near 0.5 regardless of input would manufacture a false null.
The positive control (`test_hiro_eval.py:95-134`, FACT — unit-tested):

- Plant a PERFECT lead (aggressor side chosen so `sign(delta_hiro_t) =
  sign(F_{t+1} − F_t)` every minute) → `lead_lag_sign_agreement` returns
  **hit_rate 1.0** (6/6 scored minutes).
- Flip every side → a PERFECT anti-lead → **hit_rate 0.0**.
- The planted-signal span is the full `[0, 1]`, not a dead band at 0.5.

So the metric **reaches both extremes on planted data → it is ALIVE.** This is what
makes the real-data near-0.5 a genuine "no strong directional edge", not a
dead-harness artefact. (8 positive-control / skip-semantics / look-ahead /
shuffle-invariance / accounting tests pass; full harness suite = **58 tests**
— 16 provenance + 20 metrics + 14 divergence + 8 hiro_eval.)

## 4. Real-data result (4 days, per-instrument, three-state — descriptive only)

> These numbers are runtime outputs of `run_hiro_eval.py` on the gitignored 0DTE
> pull (session-verified by the test-author positive-control + the red-team
> aggregation review; **not reproducible from committed files**). They are
> **descriptive over n=4 correlated days incl. a crash arc — NOT evidence.**

**The red-team caught a real defect:** the first aggregation **pooled ES + NQ**,
and a single low-coverage NQ row could flip the band and mask a consistent ES
result. The fix aggregates **per-instrument**, n-weights the control gap (a
66-minute day must not count like a 385-minute day), and gates on forward coverage
before classifying (`run_hiro_eval.py:356-397`, `_classify` `399-437`). The
classifier is three-state and **never collapses "underpowered" into "null"**
(`run_hiro_eval.py:399-409`, `475-480`).

Result, per instrument, per horizon `k ∈ {5,15,30}` minutes:

- **k=15 and k=30 — NULL (ES, adequate coverage).** No edge over shuffle: the
  per-day sign of `real_minus_shuffle` is inconsistent across the 4 days and the
  n-weighted mean gap is ~`+0.01` / ~`0`. A genuine flat gap on adequate coverage,
  not an inability to resolve.
- **k=5 — ES = SUGGESTIVE-POSITIVE but AT-THRESHOLD and UNDERPOWERED.** All 4 ES
  days positive (4/4), n-weighted mean `real_minus_shuffle` ~`+0.047`, per-day band
  ~`[+0.03, +0.06]`, forward coverage `0.99`. But the mean sits just **below** the
  `EDGE_THRESH = 0.05` bar AND `n_days = 4 < MIN_DAYS_FOR_EDGE = 5`, so the
  classifier returns **UNDETERMINED (suggestive but underpowered)**, NOT EDGE
  (`run_hiro_eval.py:108-123`, `421-431`). It is a hint, not a demonstrated edge.
- **k=5 — NQ = UNDETERMINED.** Forward coverage is too low to resolve edge-vs-null
  (as low as `0.43`, below the `COVERAGE_OK = 0.60` floor), so NQ k=5 cannot be
  called either way (`run_hiro_eval.py:415-419`).

**HEADLINE (derived, do NOT strengthen): NOT a demonstrated edge, and NOT a
demonstrated absence.** Some cells are underpowered/UNDETERMINED, which is a
distinct state from "no edge" (`run_hiro_eval.py:492-500`).

### On the user's "≥ 55%" target

The eval was **reported, not chased.** Raw hit-rates land ~`0.50–0.52`, and the
shuffled control reaches comparable values — so a raw 55% would be **meaningless
without the shuffle gap**. The only meaningful quantity (the control gap) is
at-threshold/underpowered at best, and does **not** support a demonstrated edge at
n=4. No threshold was tuned to hit any target; `EDGE_THRESH`/`SUGGESTIVE_THRESH`/
`COVERAGE_OK`/`MIN_DAYS_FOR_EDGE` are fixed in the code and printed at runtime.

## 5. Limits (explicit — some NEEDS-VERIFICATION beyond this run)

- **n = 4 correlated days**, one a crash arc — far too small for an edge claim; the
  `MIN_DAYS_FOR_EDGE = 5` gate exists precisely so a consistent ES hint cannot be
  upgraded to EDGE here.
- **The forward is an OPTION-DERIVED put-call-parity forward, NOT a traded futures
  price** (`fwd = atm + (call_mid − put_mid)`; `run_hiro_eval.py:22-31`,
  `parity_forward` `126-150`). There are no futures trades/bbo on disk. So "price"
  here is a parity reconstruction, not /ES itself.
- **NQ is underpowered by forward coverage** (0.43–0.75) — its bbo-1m did not yield
  a clean per-minute parity forward often enough to score.
- **Only `k ∈ {5, 15, 30}` minutes on a per-minute grid were tested**
  (`run_hiro_eval.py:92`). Sub-minute (trade-time) leads and horizons > 30 min are
  **unmeasured** (NEEDS-VERIFICATION — not claimed either way).

## 6. Verdict and what it means

**NOT a demonstrated edge, NOT a demonstrated absence.** k=15/30 are NULL on
adequate-coverage ES; ES k=5 is a small, at-threshold, underpowered hint (4/4 days
positive, n-wtd gap ~+0.047) worth re-testing **IF** a properly-powered, decorrelated
run with a real futures price ever happens — but the user **dropped the ~90-day
forward run**, so this stays exploratory and nothing is promoted. NQ k=5 is
unresolved on coverage.

This is a **mechanism** result, not signal validation. HIRO stays EXPERIMENTAL,
lives alongside (never replacing) the locked VOL-GEX, and is **not price-validated**.

## 7. What this is / isn't

- **Is:** a look-ahead-free (by HIRO's t-causal construction), provenance-guarded,
  unit-tested, control-anchored predictive *probe* whose harness is PROVEN alive by
  a planted positive control, with a per-instrument three-state classifier that
  keeps "underpowered" separate from "null".
- **Isn't:** a validated signal, a futures-price backtest, or a basis to claim HIRO
  predicts /ES. 4 correlated days; the forward is a parity reconstruction; NQ is
  coverage-underpowered; the k-set is narrow.
- **Deferred (the user dropped it):** a properly-powered, decorrelated forward run
  with a traded futures price, plus sub-minute and longer-horizon leads. Until then
  the ES k=5 hint is a flag, not a finding.
- **Separately deferred (backend chore, NOT this eval):** the live-worker HIRO
  accumulation fix (worker re-prices the whole tape at the current forward each
  minute, diverging from the generator's frozen-increment semantics; see
  [`../../08-status-and-gaps.md`](../../08-status-and-gaps.md) gap #4). This eval
  runs on the offline/generator-correct path, not the worker, so it is unaffected.

See also: [`ddoi-structural-eval.md`](ddoi-structural-eval.md),
[`validation-harness.md`](validation-harness.md),
[`symbology-0dte-findings.md`](symbology-0dte-findings.md).
