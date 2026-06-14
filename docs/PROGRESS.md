# PROGRESS — Heavy-Task Build (resume here in a new session)

> **NEW SESSION: read this file + `git log --oneline -15` FIRST, before touching
> anything.** This tracks the multi-point heavy build the user approved 2026-06-13.
> Heavy/assumption items follow the EXTENDED workflow (see memory
> `flowdesk-heavy-task-workflow`): creative → evidence → creative → validate →
> audit → validate → match-project → document → execute → validate → document.
> Light items follow the standard red-team cycle. Update this file at EVERY
> completed point / meaningful checkpoint.

## Permanent opus subagents available (`.claude/agents/`)
- **redteam-auditor** — adversarial attacker (break the claim).
- **contract-guardian** — pydantic↔zod↔CONTRACT.md mirror parity.
- **quant-greeks-auditor** — dimensional analysis, sign conventions, scale constants,
  finite-difference, reduction properties, look-ahead/confound. USE for every
  formula in this build.

## Hard rules (unchanged)
LOCKED CONTRACT / VOL-GEX-DEX / `schema_version=1` untouched. New fields additive,
optional, nullable, EXPERIMENTAL, alongside (never replacing) VOL-GEX. Mirror
lockstep. No new Databento pull. Trust-but-verify diffs; tests green before "done".

## Verify commands
```
# engine:   cd services/engine && PYTHONPATH=src ../../.venv/Scripts/python.exe -m pytest -q
# api:       cd services/api && PYTHONPATH=src:../engine/src ../../.venv/Scripts/python.exe -m pytest -q
# contracts: cd packages/contracts && node_modules/.bin/tsc --noEmit && node_modules/.bin/tsx scripts/validate.ts
# harness:   .venv/Scripts/python.exe -m pytest analysis/harness/test_metrics.py -q
# golden regen ONLY if intentional: edit additively by hand (env float churn — do NOT commit noise)
```

## Baseline at start of this build
HEAD `1131d9b`. Engine 172 pass, API 78 pass, harness 17 pass, contracts tsc+validate clean.

---

## The plan (in build order) + status

| # | Item | Workflow | Status |
|---|------|----------|--------|
| 1 | Synthetic-OI **#7 total-hedging** (gamma+charm+vanna on Q base) | heavy | ✅ DONE (commit pending) |
| 2 | **SVI / expected-move** wiring (gap #5 remainder) | heavy | ✅ DONE (commit pending) |
| 3 | **OI-aware wall-validation** pass in harness (gap #1 remainder) | heavy | ✅ DONE (commit pending) |
| 4 | Synthetic-OI **#6 size-tiered** (needs per-trade-tape refactor) | heavy | ✅ DONE (commit pending) |
| 5 | Synthetic-OI **#5 decay-weighted** (needs HiroTrade.ts + #6 refactor) | heavy | ✅ DONE (commit pending) |
| 6 | **Baseline lint/type cleanup** (gap #6) | light | ✅ DONE (commit pending) |
| D | **DDOI engine** — same-session, EXPERIMENTAL, alongside VOL-GEX (NOT cross-day; proven impossible on 0DTE) | heavy | ✅ DONE (commit pending) |
| P | **Proprietary metrics** (Volatility Trigger / Hedge Wall / Risk Pivot etc.) — reverse-engineered, labelled approximation | heavy | ✅ DONE (commit pending) |

Legend: ⏳ not started · 🔨 in progress · ✅ done+pushed · ⚠️ blocked

---

## Checkpoint log (append newest at top)

### 2026-06-14 — VT gamma-concentration DISTINCTNESS GATE → FAIL → DO-NOT-BUILD (option a, data-backed)
The third agreed step (VT concentration-gamma research). Investigated — read-only,
no code — whether a faithful *local-positive-gamma-distribution* VT (the real
SpotGamma description, which `oi_gamma_flip` is NOT) is worth building HONESTLY as a
new EXPERIMENTAL field. **The gate FAILED. Decision: DO NOT BUILD. Nothing was built,
nothing was validated.** This CLOSES the VT question with a data-backed negative.

**Role-separated flow (anti-bias):** creative + research-expert designed the framing
and surfaced the ONE parameter-free candidate worth gating (C-5) → research-expert ran
a read-only DISTINCTNESS GATE on the 4 on-disk 0DTE days × ES/NQ = 8 cells, decoded
THROUGH the `assert_session_iids_0dte` tenor-provenance guard. No coder stage (nothing
built). Orchestrator decided under the human's standing "go to c only if good".

**VERIFIED facts (do NOT soften):**
- **THE USER'S INTUITION WAS CORRECT.** SpotGamma's VT is a LOCAL positive-gamma-
  *distribution* object ("konsentrasi gamma positif … last major level of positive
  gamma support", explicitly NOT a simple crossover; `mega-riset2.md:114-116`), and
  FlowDesk's five existing levels (`oi_gamma_flip`, `abs_gamma_strike`, `hedge_wall`,
  call/put wall) all MISS that shape (global argmax or cumulative zero-cross). So
  "`oi_gamma_flip` is just an OI crossover, not VT" was a FAIR criticism.
- **BUT a faithful VT is not buildable honestly.** Its "major/last" qualifier is a
  threshold τ settable ONLY by matching SpotGamma's published SPX numbers
  (`mega-riset2.md:130`, H-B2 conf 55%, "τ perlu kalibrasi"), which the /ES-GLBX
  universe cannot obtain — calibrating τ to vendor numbers is
  inference-dressed-as-reproduction (the documented catastrophic failure mode,
  `reference/methodology-decisions.md`). Faithful VT declined (already on record).
- **The ONE parameter-free candidate, C-5:** `VT_exp = argmax over K<F with
  net_oi_gamma(K)>0 of net_oi_gamma(K)` — strongest dealer-long-gamma strike below F.
- **GATE RESULT: FAIL.** C-5 is **UNDEFINED (None) on 6 of 8 cells** (usually no
  positive-net-gamma strike below F). On the 2 computable cells: **06-08 NQ (29600)
  collapses onto BOTH `hedge_wall` AND `abs_gamma_strike`** (a relabel); **06-05 ES
  (7380) is ordinally broken** — sits BELOW its own `put_wall` (7400), violating the
  expected `put_wall <= VT <= oi_gamma_flip < F`. Zero cells ordinally sane; placement
  jumpy (F−C5 distance 1.3 vs 5.8 strike-steps). Not a stable level.
- **STRUCTURAL REASON (INFERENCE, high):** Black-76 gamma ~symmetric per strike ⇒
  `net_oi_gamma(K) ~ g(K)·(OI_call − OI_put)`; a positive value strictly below F needs
  call-OI > put-OI below the forward, rare (downside is put-OI-dominated). C-5 fires
  only on a stray call-heavy strike — an artefact, not a level.
- **HEADLINE:** C-5 is WORSE than the `oi_gamma_flip` relabel, not better.

**DECISION (orchestrator, with the human's "go to c only if good"):** DO NOT BUILD any
gamma-concentration / VT-like level. `oi_gamma_flip` keeps its honest name. No
predictive arm was even reachable (OI is EOD-settle, look-ahead-blocked like
synthetic-OI; the ~90-day validation run is dropped), so even a passing gate could
never have been price-validated. VT investigation CLOSED — data-backed NOT-VALIDATED
negative.

**Docs changed (markdown only):** `docs/08-status-and-gaps.md` (gap #2 proprietary /
`oi_gamma_flip` section — added the distinctness-gate UPDATE), this checkpoint. **NO
non-markdown touched.**

**NEXT:** the three agreed steps (HIRO predictive eval, synthetic-OI #4 flow-term eval,
VT gamma-concentration) are now ALL DONE/closed. Remaining OPEN items are the DEFERRED
backend chores — the live-worker HIRO accumulation unify (Gap #4) and synthetic-OI
#5/#6/#7 evals + FE-wiring (couples to Gap #4) — which are separate and AWAIT USER
DIRECTION. Nothing here was built; nothing was validated.

### 2026-06-14 — Synthetic-OI #4 FLOW-TERM eval built (controlled, EOD STRUCTURAL) — BOTH /ES + /NQ UNDETERMINED, validated NOTHING, no 55%
A STRUCTURAL (NOT predictive) eval of the ONE thing synthetic-OI #4 uniquely claims
over a classic OI-GEX vendor: does the native-aggressor FLOW term `(−flow)·w` add
per-strike STRUCTURE OVER pure OI-GEX? **This validated NOTHING** — it is an honest
exploratory UNDETERMINED for both instruments at n=4. **There is NO hit-rate / NO
"55%"** (structural arm — a predictive arm is BLOCKED: synthetic `Q` needs
prior-session `OI_open`, the only OI on disk is same-day EOD settle, settle-OI
intraday is look-ahead, and 0DTE has zero cross-day overlap).

**Role-separated flow (anti-bias):** **the-advisor** corrected the comparison axis
off the confounded "synthetic vs VOL" (which mixes the LOCKED OI-vs-VOL basis decision
#1 with the flow term, and is possibly trivial) onto the only unique claim —
**`gex` (w=1) vs `gex_static` (w=0)** → coder built → **test-author** anchored the new
sign-free aggregator → **red-team** caught a single-day-artefact "NQ YES" + a missing
sign-consistency gate → coder sign-gate fix → **74 tests pass** (16 provenance + 20
metrics + 14 divergence + 8 hiro_eval + 16 synthetic_oi_eval).

**Built (NOT touched by doc-scribe — built this session by the coder):**
- `analysis/harness/synthetic_oi_eval.py` (pure core) + `run_synthetic_oi_eval.py`
  (dbn runner, through the fail-closed tenor-provenance guard) +
  `test_synthetic_oi_eval.py` (16 tests).

**VERIFIED facts (do NOT soften):**
- **AGGREGATOR ANCHOR holds (load-bearing):** `sum(synthetic_gex_by_strike(...))`
  == engine scalar `synthetic_gex(...)` EXACTLY (`math.isclose`) at w=0/0.5/1.0
  (`test_synthetic_oi_eval.py:118-132`). NO double-sign — a NEW sign-free aggregator
  was written (not `ddoi_divergence.gex_by_strike`, which would re-apply the dealer
  sign already baked into `Q` and manufacture fake divergence;
  `test_synthetic_oi_eval.py:168-188`). This is what makes the eval trustworthy.
- Metrics: `residual_r2` (is `gex` a scalar rescale of static), `flow_norm_ratio`
  (headline magnitude), `argmax_distance`, vs a shuffled-aggressor-sign null. The DDOI
  `Σw=0` sign-flip detectors were deliberately NOT used (wrong mechanism — synthetic
  has no de-meaning).
- **RESULT (per-instrument, never pooled):** the flow term is **materially-sized**
  (mean `flow_norm_ratio` ~0.5 /ES, ~0.79 /NQ) but its DIRECTION is **NOT separable**
  from random-sign flow of the same magnitude at n=4. **/ES = UNDETERMINED** (per-day
  gaps {−0.017, −0.025, +0.171, −0.010}, mean +0.030 < 0.05, sign 1+/3− inconsistent).
  **/NQ = UNDETERMINED** (per-day {+1.017, +0.277, −0.401, −0.479}, mean +0.103 — but a
  **single-day artefact**: 06-05's +1.017 is ~245% of the signed sum, excluding it mean
  = −0.201, sign 2+/2− inconsistent).
- **HEADLINE: NOT a demonstrated edge, NOT a demonstrated absence.** NQ NEVER reads YES.

**Verdict-logic bug found + fixed:** the runner had **no per-day sign-consistency
gate**, so the NQ magnitude-mean (dominated by one thin-profile day) read "YES
(exploratory)". The red-team caught it; fixed by adding the per-day sign tally +
single-day-domination check (`run_synthetic_oi_eval.py:115-151`, `455-473`) — the
**same defect CLASS** as the earlier HIRO ES+NQ-pooling defect. Structural lesson: a
magnitude-mean dominated by one high-variance thin-profile day must never override a
coin-flip per-day sign.

**VERIFIED vs DEFERRED:** only **#4** (`gex` vs `gex_static`) was evaluated. **#5
decay / #6 tiered** are DEFERRED — the offline harness builds only ONE flow map; the
tier/decay maps exist only in the live worker. **#7 total_hedging** DEFERRED — its
`gamma_hedge` == #4 `gex` bit-for-bit (`total_hedging.py:17,62`), so only
`charm_hedge`/`vanna_hedge` are novel + unevaluated. The synthetic-OI family is still
**ABSENT from committed FE session JSON** (live-worker only; couples to the
not-yet-built Gap #4 dashboard).

**Docs changed (markdown only):** `docs/research/empirical/synthetic-oi-eval.md`
(NEW), `docs/08-status-and-gaps.md` gap #2 (structural-eval UPDATE), this checkpoint.
**NO non-markdown touched.**

**NEXT:** VT concentration-gamma research (the third agreed step) — investigate
whether a τ-concentration "faithful VT" is buildable, vs the relabeled OI-basis
`oi_gamma_flip` already shipped (gap #2 proprietary notes). Plus the DEFERRED #5/#6/#7
follow-ups + synthetic-OI FE-wiring (couples to Gap #4).

### 2026-06-14 — HIRO t→t+k PREDICTIVE eval built (controlled, look-ahead-free) — exploratory NULL / underpowered-hint, validated NOTHING
The first *predictive* eval of any FlowDesk lens. HIRO earns it (DDOI did not):
HIRO is strictly t-causal (`Σ_{trades≤t} sign·δ·size·M·F`), so a `delta_hiro_t →
sign(F_{t+k}−F_t)` test is **legitimately look-ahead-free** (predictor uses `≤t`,
outcome `>t`) — unlike DDOI, whose whole-day-normalized `Σw=0` weight is look-ahead-
contaminated per-minute. **This validated NOTHING** — it is an honest exploratory
null / underpowered-hint; only a properly-powered forward run (dropped by the user)
could validate.

**Built (markdown-adjacent code, NOT touched by doc-scribe — built earlier this
session by the coder):**
- `analysis/harness/hiro_eval.py` (pure core) + `run_hiro_eval.py` (dbn runner,
  through the fail-closed tenor-provenance guard) + `test_hiro_eval.py` (8 tests).
  Full harness suite = **58 tests pass** (16 provenance + 20 metrics + 14 divergence
  + 8 hiro_eval).
- THE CONTROL GAP IS THE HEADLINE, never the raw hit-rate: `real − mean(shuffled-
  aggressor-sign)` + signed-volume / contemporaneous / persistence controls. Verdict
  line DERIVED from computed gaps, never hardcoded.

**Role-separated flow (anti-bias):** creative + expert designed (t-causal ⇒
predictive-legitimate; control-gap-is-headline) → coder built → **test-author**
positive-control (planted perfect lead ⇒ hit_rate 1.0; anti-correlated ⇒ 0.0 ⇒
harness ALIVE, not stuck at 0.5) + **red-team** caught that pooling ES+NQ masked the
signal → coder aggregation fix (per-instrument, n-weighted gap, coverage-gated
three-state classifier; "underpowered" NEVER collapsed into "null") → 58 tests pass.

**VERIFIED facts (do NOT soften):**
- HARNESS ALIVE: `test_positive_control_metric_is_alive` (`test_hiro_eval.py:95-134`)
  — metric reaches the full `[0,1]` on planted data ⇒ the real near-0.5 is a genuine
  "no strong edge", not a dead-metric artefact.
- Per-instrument three-state result (descriptive, n=4 correlated days, OPTION-DERIVED
  parity forward — NOT a futures price): **k=15/30 = NULL** (adequate-coverage ES,
  sign inconsistent, n-wtd gap ~+0.01/~0); **k=5 ES = SUGGESTIVE-POSITIVE but
  AT-THRESHOLD + UNDERPOWERED** (4/4 ES days positive, n-wtd gap ~+0.047, band
  ~[+0.03,+0.06], fwd_cov 0.99, but n_days=4 < 5 ⇒ NOT an edge); **k=5 NQ =
  UNDETERMINED** (fwd coverage as low as 0.43).
- **HEADLINE: NOT a demonstrated edge, NOT a demonstrated absence.** A raw 55% would
  be meaningless without the shuffle gap; the eval was REPORTED not chased
  (thresholds fixed in code, printed at runtime).

**LIMITS (red-team NEEDS-VERIFICATION):** n=4 correlated; parity forward not futures;
NQ coverage-underpowered; only k∈{5,15,30}min tested (sub-minute / >30min unmeasured).

**DEFERRED / NOT validated:** the ~90-day forward run was **dropped by the user** ⇒
the ES k=5 hint stays a flag, not a finding. The **live-worker HIRO accumulation fix
remains DEFERRED** (separate backend chore; this eval runs on the offline/generator-
correct path, not the worker). Nothing was price-validated.

**Docs changed (markdown only):** `docs/research/empirical/hiro-predictive-eval.md`
(NEW), `docs/08-status-and-gaps.md` gap #4 (predictive-eval UPDATE), this checkpoint.
**NO non-markdown touched.**

**NEXT:** synthetic-OI eval (same controlled pattern — pure core + dbn runner +
positive-control + shuffle/contemporaneous controls + three-state per-instrument
verdict); the DEFERRED live-worker HIRO fix + synthetic-OI FE-wiring chores (both
couple to the not-yet-built Gap #4 dashboard).

### 2026-06-14 — Audit follow-ups: surface honesty fix DONE; #4 residual RESOLVED; HIRO #2 + synthetic-OI #3 DEFERRED (advisor-revised plan)
Resolution of the 4 open follow-ups from the prior audit checkpoint. **the-advisor's
SECOND gate run materially revised the plan** — it showed the naive HIRO
"make-persistent" fix would trade a cosmetic parity bug for a restart-correctness
bug, and that follow-up #4 was already answerable from the code — so the orchestrator
REVERSED course: deferred #2 rather than rushing a live-worker rewrite for a
not-yet-built consumer. **This turn improved HONESTY (surface) + closed a residual,
but validated NOTHING — only the ~90-day forward run validates any lens.**

**The 4 follow-ups, resolved:**
1. **surface `arb_free` overclaim — DONE.** Renamed `arb_free -> variance_nonneg`
   across the mirror; the flag now honestly tests only `w(k) >= 0` (non-negative
   implied variance), NOT butterfly/density `g(k) >= 0`; the false docstring promise
   of a separate `g(k)` check was removed (Durrleman `g(k) >= 0` deliberately NOT
   implemented — lens unvalidated). Commit **`d4f24e8`**. NON-BREAKING (required
   sub-key in the optional EXPERIMENTAL Surface block; `schema_version` stays **1**;
   no committed fixture carried `arb_free` => zero regen / zero data pull).
   contract-guardian: **MIRROR CONSISTENT** (10/10 Surface fields). engine 199 pass,
   tsc + validate clean.
2. **HIRO worker/generator divergence — DEFERRED with design direction.** FACT +
   the-advisor: NOT an accumulation-method bug — both paths accumulate the same trade
   set `[open, ts]`. The real gap is the FORWARD per trade: the live worker
   (`worker.py:264`) re-prices the whole day's tape at the single current-minute
   forward `F_t`; the generator (`gen_session_snapshots.py:75-112`) freezes each
   trade's increment at its arrival-minute forward via a persistent `HiroState`
   (the economically-correct semantics). DEFER: HIRO's only consumer is the FE render
   (Gap #4, not being built now); and the naive fix would trade the parity bug for a
   RESTART-correctness bug — the current stateless rebuild-from-`[open, ts]` is
   restart/gap/STALE-safe (`worker.py:203-208`), a persistent `HiroState` is not
   without explicit reset/recovery/gap handling. DESIGN DIRECTION recorded: keep the
   accumulator in the api-layer worker (NEVER push `HiroState` into `build_snapshot`
   — engine purity locked); feed only NEW trades at each minute's forward; design
   reset/restart/gap explicitly; lock both-paths-equal with an independent test;
   grep golden + worker tests for pinned HIRO values first.
3. **synthetic-OI absent from FE JSON — DEFERRED.** FACT: #4/#5/#6/#7 are wired in
   the live worker (`worker.py:394-397`) but NOT in `gen_session_snapshots.py`
   (`:113-118` passes only `ohlc`/`hiro`), so they are absent from committed FE
   session JSON. SAME worker/generator parity class as #2. DEFER: couples to the Gap
   #4 dashboard decision — no point generating data the FE does not render. When Gap
   #4 is built, wire the generator to pass `net_flow`/`net_flow_tiered`/
   `net_flow_decay` for whichever lenses the dashboard shows.
4. **`_fetch_signed_trades` window — RESOLVED.** FACT: the window IS
   cumulative-since-RTH-open, NOT per-minute. `_fetch_signed_trades` ->
   `feed.get_hiro_trades`; `historical.py:229-260` window = `[rth_open, ts+1min)`
   with filter `if event < rth_open or event >= end: continue`, docstring "over the
   RTH window `[open, ts]`". So the #5 decay-age math and HIRO accumulation rest on
   the documented cumulative-since-open basis. Residual closed (confirmed, not a bug).

**VERIFIED this session:** surface rename (commit `d4f24e8`, code grep +
contract-guardian CONSISTENT); follow-up #4 (read-only, `historical.py:229-260`);
the-advisor read-only gate + coder + contract-guardian. **DEFERRED / NOT validated:**
HIRO #2 + synthetic-OI #3 (both couple to the not-yet-built Gap #4 FE); nothing was
price-validated — only the ~90-day forward run (Gap #1) validates any lens.

**Docs changed (markdown only):** `docs/08-status-and-gaps.md` (gap #2 residual
RESOLVED + synthetic-OI FE-wiring DEFERRED; gap #4 HIRO DEFERRED-with-design-direction;
gap #5 surface `variance_nonneg` DONE), this checkpoint. **NO non-markdown touched.**

**NEXT:** await user decision on Gap #1 forward-run / Gap #4 frontend.

### 2026-06-14 — Audit of the 6 remaining EXPERIMENTAL lenses + `oi_gamma_flip` rename + advisor first-run
Role-separated audit pass (NO build beyond the already-committed rename). The 6
remaining un-dissected EXPERIMENTAL lenses were audited read-only by
**quant-greeks-auditor**, gated upstream by **the-advisor** (its FIRST gate run).
These are honest verdicts; two are DOWNGRADES and must NOT be softened. **This audit
found defects to FIX but validated NOTHING — only the ~90-day forward run validates.**

**the-advisor first-run (anti-bias gate):**
- Caught a **PHANTOM `schema_version` HOLD** on the `volatility_trigger -> oi_gamma_flip`
  rename: it is a key-string change with no wire/shape change, so it is non-breaking
  and `schema_version` stays **1**. (contract-guardian: **CONSISTENT**.)
- Caught **HIRO missing from the audit scope** — added it; HIRO then surfaced a real
  DOWNGRADE (below).
- Moved `total_hedging` into the synthetic-OI group (it is #7 on the Q base, not a
  standalone lens).
- The orchestrator replied to **every** counsel point (no silent drops).

**The 4 audit verdicts (each by quant-greeks-auditor, file:line):**
1. **VEX/CHEX (`exposure_ext.py`) — SOUND.** Dimensions correct (vanna/charm get ONE
   `F`; VEX `0.01` = vol-point scale, not GEX's price-move `0.01`; CHEX `1/365`
   per-day). Signs match `black76` (vanna call==put, charm call!=put). FD tests pass
   (71). Thin skipped. Additive, `schema_version` untouched. ONLY caveat (already
   EXPERIMENTAL): sign->regime "stabilising/destabilising" semantics reuse GEX's color
   meaning — only the 90-day run backs that; FE must show the caveat and must NOT let
   VEX/CHEX drive the regime classifier.
2. **synthetic-OI #4/#5/#6/#7 (`synthetic_oi.py`,`total_hedging.py`) — SOUND math,
   LIVE-ONLY reach.** Reductions hold (#6->#4 at tier=1.0; #5->#4 at `half_life<=0`;
   #4 `w->0` -> pure OI-GEX). In the live worker the 3 flow maps ARE distinct (tiered
   drops retail at `RETAIL_TIER_WEIGHT=0.0`, block ×1.5; decay reweights by recency +
   drops ts-less trades) — NOT a collapse-to-#4 in live. **FACT:** family computed
   ONLY in the live worker (`worker.py:394-397`); `gen_session_snapshots.py:113-118`
   passes NO `net_flow*`, so #4/#5/#6/#7 are **ABSENT from the committed FE session
   JSON**. **#7 `gamma_hedge` == #4 `gex` bit-for-bit** (only `charm_hedge`/
   `vanna_hedge` novel). RESIDUAL (could-not-verify): worker `_fetch_signed_trades`
   window cumulative-since-RTH-open vs per-minute — flag for confirmation.
3. **surface.py (SVI + expected-move) — DOWNGRADE (`arb_free` overclaim).** EM
   dimensionally sound (`F·σ·sqrt(T)`, T cancels on 0DTE). Thin handled (None). WIRED +
   additive (the gap-map "isolated" note is now STALE — surface IS consumed:
   `with_surface=True` at `worker.py:399` + `gen_session_snapshots.py:116`). THE
   DOWNGRADE: `is_butterfly_arbitrage_free` (`surface.py:130-145`) only tests
   `w(k)>=0`, NOT `g(k)>=0`; the promised `g(k)>=0` density check (`surface.py:28`)
   DOES NOT EXIST. So a steep `b·(1+|ρ|)` slice can pass `arb_free=True` yet carry
   butterfly arb. FIX (record, do not perform): implement Durrleman `g(k)>=0`, OR
   rename to `variance_nonneg` + downgrade the wording.
4. **hiro.py — DOWNGRADE (consistency defect, NOT look-ahead).** Dimensionally sound
   (greek-weighted dealer delta-notional USD, `×M×F`). Aggressor sign `B/A/N->+1/-1/0`
   correct, no double-sign. **Strictly t-causal** — window `[rth_open, ts+60s)`, real
   daily reset, per-trade ts threaded; NO look-ahead. THE DOWNGRADE: the live worker
   (`worker.py:264`) RE-PRICES the whole day's tape at the single current forward
   `F_t` every minute -> cumulative HIRO drifts on zero-trade minutes and DIVERGES
   from the offline generator (`gen_session_snapshots.py:75-112`), which FREEZES each
   trade's increment at its arrival-minute forward via a persistent `HiroState`.
   Worker and generator render DIFFERENT HIRO lines for the same session. FIX (record,
   do not perform): unify accumulation — worker should use a persistent `HiroState`
   fed only NEW trades at each trade's arrival forward. **Must fix before the FE
   renders HIRO.**

**The rename (committed):** `volatility_trigger -> oi_gamma_flip` is commit
**`e022fd7`** — honestly names the method (a gamma flip on the OI basis, NOT
SpotGamma's VT). contract-guardian: **CONSISTENT**, `schema_version` stays **1**.
Field reads `oi_gamma_flip` across `proprietary.py`/`schema.py`/`snapshot.ts`/
`CONTRACT.md`/tests/golden (verified read-only).

**VERIFIED this session:** the 4 verdicts above (by quant-greeks-auditor) + the
rename (commit `e022fd7`, code grep + contract-guardian CONSISTENT). **DEFERRED /
NOT validated:** nothing was price-validated — only the ~90-day forward run (Gap #1)
validates any lens. The audit's job was correctness/consistency, not edge.

**OPEN FOLLOW-UPS (need a HUMAN decision):**
- **surface `arb_free`** — implement Durrleman `g(k)>=0` OR rename to
  `variance_nonneg` + downgrade docstring/schema. (Markdown-only here; no code change.)
- **HIRO accumulation** — unify worker to a persistent `HiroState` so worker == generator;
  prerequisite before the FE renders HIRO.
- **synthetic-OI FE wiring** — `gen_session_snapshots.py` passes no `net_flow*`, so the
  family is absent from committed FE sessions; decide whether to wire it.
- **`_fetch_signed_trades` window** — confirm cumulative-since-RTH-open vs per-minute.

**Docs changed (markdown only):** `docs/08-status-and-gaps.md` (gap #2 synthetic-OI
live-only + rename note; gap #4 HIRO divergence DOWNGRADE; gap #5 VEX/CHEX caveat +
surface `arb_free` DOWNGRADE), this checkpoint. **NO non-markdown touched.**

**NEXT:** await user decision on the 4 open follow-ups above + Gap #1 forward-run.

### 2026-06-14 — Fase 2: `volatility_trigger` dissection (NO BUILD)
A DISSECTION of `engine/proprietary.py` `volatility_trigger`, **not a build** —
nothing was built; the honest finding is recorded and a rename decision is escalated.

**Role-separated flow (anti-bias):** research-expert (archive read) + creative
(reframe) verified the finding this session; orchestrator grepped the consumer
surface. No coder stage (nothing built).

**VERIFIED facts:**
- VT-as-coded (`proprietary.py:93`) is **algorithmically IDENTICAL** to the locked
  `levels.gamma_flip` (`levels.py:139`) — cumulative net-gamma zero-crossing + linear
  interpolation; the ONLY difference is the input basis (OI-gamma vs VOL-gamma). So VT
  is "gamma-flip on the OI basis" — a **RELABEL**, not SpotGamma's Volatility Trigger.
- The research archive distinguishes VT from the gamma-flip but gives **NO reproducible
  formula** for SpotGamma's VT — only a negative/ordinal description ("NOT a simple
  crossover," last major positive-gamma support, above the Put Wall and below Zero
  Gamma; `riset-spotgamma.md:266`, `mega-riset2.md:114-116,145`). Every computable
  candidate (H-B2 τ-threshold positive-gamma strike `mega-riset2.md:130`, conf 55%;
  H-B3 argmax dGamma/dS, conf 35%) is **sub-60%-confidence inference** needing a τ
  calibrated to SpotGamma's published VT numbers.
- FlowDesk's ES/GLBX universe structurally cannot match the SPX-vendor's VT numbers ⇒
  a "faithful VT" has **NO validation target** (inference-dressed-as-reproduction, the
  project's documented catastrophic failure mode). **DECISION: do NOT build a faithful
  VT.** The τ-concentration level is **DEFERRED** until the gap-#1 90-day harness can
  rank it; even then τ must never be tuned to vendor numbers nor named/claimed as
  SpotGamma's VT.

**Consumer surface (orchestrator grep):** `volatility_trigger` is consumed by
`engine/proprietary.py`, the contract mirror (`schema.py:310` ↔ `snapshot.ts:259,490`
↔ `CONTRACT.md:288`), and tests (`test_proprietary.py`, `test_snapshot.py`) + golden.
**NO frontend (`apps/web`) consumer reads it.** A rename is mechanical across the
mirror + tests + golden.

**ESCALATION (HUMAN decision, not an agent's):** renaming `volatility_trigger` →
e.g. `oi_gamma_flip` is a **BREAKING CONTRACT CHANGE** ⇒ `schema_version` implication
(locked contract). Presented to the user with options: **(a) rename** /
**(b) keep + honest-label** / **(c) defer the τ-build to the 90-day harness**. Being
escalated, not done.

**Next:** await user decision on the rename + the Gap #1 forward-run.

### 2026-06-14 — Fase 1: DDOI same-session structural eval (0DTE) — INCONCLUSIVE-leaning-redundant
Mechanism / structural result, **NOT signal validation**. The first 0DTE-valid
evaluation of DDOI (the WITHDRAWN cross-day "49.2/50.8" was quarterly contamination;
cross-day ΔOI is impossible on 0DTE). It asks ONE contemporaneous, look-ahead-free
question — *is DDOI-GEX structurally different from VOL-GEX, or does it collapse to
~±VOL?* — and answers **INCONCLUSIVE-leaning-redundant** at n=4.

**Built:**
- `analysis/harness/ddoi_divergence.py` (NEW, pure core) + `run_ddoi_divergence.py`
  (NEW, dbn runner, runs THROUGH the fail-closed tenor-provenance guard) +
  `test_ddoi_divergence.py` (NEW, 14 tests). Full harness suite = **50 tests pass**
  (16 provenance + 20 metrics + 14 divergence).
- EOD / whole-session profiles only, no outcome scored ⇒ look-ahead-free by
  construction. **NOT predictive**: the time weight `w(i)=1−2·i/(n−1)` is
  whole-day-normalized (needs `n`=full-day trade count), so per-minute predictive use
  is look-ahead-contaminated — explicitly out of scope.

**Role-separated flow (anti-bias):** creative + expert designed → coder built →
red-team + quant-greeks-auditor caught the **sign-flip artefact** (numeric derivation
+ read-only 4-day diagnostic) → coder upgraded the discriminator
(`magnitude_pearson` / `best_fit_scalar_c` + `residual_r2` / `leg_timing_diagnostic`)
→ test-author locked it (14 tests) → engine `ddoi.py` docstring corrected
(docstring-only; engine 199 tests still pass).

**VERIFIED facts:**
- `Σ w(i) = 0` (n≥2) ⇒ `ddoi_leg = Σ w(i)·|size|` is a **de-meaned volume
  timing-skew** statistic, NOT a contracts-outstanding ΔOI. Back-loaded dominant
  legs ⇒ DDOI-GEX ≈ **−c·VOL-GEX** (same strikes, flipped sign).
- Real data (n=4, descriptive, incl. crash arc): signed pearson ≈ **−0.34**,
  aggregate `magnitude_pearson` ≈ **0.285**, **BIMODAL** (2/8 rows NQ 06-08 / NQ
  06-10 textbook sign-flip-redundant, `|mag r|`≈0.93–0.98, `residual_r2`≈0.86–0.95;
  rest low-magnitude/noise); `mean_late_share` ≈ **0.34** (back-loading NOT uniform).
- **Verdict (do NOT strengthen): INCONCLUSIVE-leaning-redundant at n=4.** The −0.34
  is mostly the mechanical sign-flip + noise, NOT new positioning info. Auditors
  advise **NOT** funding the ~90-day predictive run on this; any 90-day run should
  FIRST be a structural disambiguation, not predictive scoring.

**DEFERRED:** a properly-powered structural disambiguation on the ~90-day forward
pull (requires the user's manual anti-lock Databento pull).

**Honest framing:** mechanism / structural, NOT signal validation. DDOI stays
EXPERIMENTAL, alongside VOL-GEX, not price-validated. Docs:
`research/empirical/ddoi-structural-eval.md` (NEW), `08-status-and-gaps.md` gap #2,
this checkpoint. **Next:** Fase 2 — `volatility_trigger` dissection.

### 2026-06-14 — Fase 0: anti-forget tenor-provenance guard (infrastructure, NOT signal)
This phase builds a fail-closed GUARD against the documented quarterly-as-0DTE
contamination — it is **anti-forget infrastructure**, NOT validation of any signal.

**Built:**
- `analysis/harness/provenance.py` (NEW) — fail-closed 0DTE tenor guard.
  `assert_0dte(legs, session_date)` raises `TenorContaminationError` on: empty set,
  non-`C`/`P` class, ET-expiry != session, >1 unique expiry, or days-to-expiry >= 1.
  `assert_session_iids_0dte(traded_iids, def_map, session_date)` resolves RAW traded
  ids against the FULL all-instrument def map (unresolved id raises) then asserts
  0DTE — the NON-TAUTOLOGICAL entry point. Returns a frozen `DataProvenance`
  (source_label, session_date, expiry_set, n_legs, instruments, sha256 fingerprint,
  realized_tenor_days). Date compare done in ET (16:00 America/New_York), not UTC.
- WIRED into `run_validation.run_day`: builds a COMBINED all-instrument flat def map,
  enumerates RAW traded+settled ids from the day's trades+statistics streams (NO
  pre-filter), and calls the guard BEFORE the empty short-circuit and BEFORE any
  metric/snapshot. Empty raw set => loud WARN + skip; non-empty with any
  non-session/unresolved id => RAISE.
- `analysis/ddoi.py` got a minimal inline expiry-vs-trade-day guard (future-proofing
  only — its quarterly input dirs no longer exist on disk, so it cannot run now).

**Role-separated flow (anti-bias):** creative + expert design → coder (code only) →
test-author + red-team (independent) → 2 correction rounds — (1) a TAUTOLOGY fix (the
first wiring validated an already-bucketed set where `expiry==session` can never
fire), then (2) a MAP-SCOPING fix (an ES-only map false-raised on clean days because
NQ ids were unresolved) — → re-verified. The guard taking two correction rounds is
the anti-bias process working, recorded honestly, not hidden.

**VERIFIED:** 36 harness tests pass (16 in `test_provenance.py` — incl. locks that an
unresolved id raises and that a combined map passes where a single-instrument map
raises; + 20 metrics). Coder's decoded real-day probe: 8/8 real-day decoded PASS on
the combined map.

**KNOWN RESIDUAL (do not soften):** only `run_validation.py` is wired through the
guard. The other duplicated loaders (`lapis1.build_iid_map`, `rerun_zerodte`,
`synthetic_oi_v2/v3/v4`, and `ddoi` via `lapis1`) are NOT yet routed (TODO list in
`provenance.py`). `ddoi.py` has its own inline check; the rest do not. The guard is
NOT yet universal.

**Honest framing:** Fase 0 is infrastructure (anti-forget), NOT signal validation.
**Next:** Fase 1 — DDOI evaluated on real 0DTE data with a same-session metric;
Fase 2 — `volatility_trigger` dissection.

### 2026-06-14 — DOC HONESTY PASS: DDOI provenance + VT method contradiction (docs only)
Role: doc-scribe (markdown only; **no non-markdown files touched**). Turned three
already-verified research findings into honest docs.

**A — Shakedown: PASS.** Re-opened every cited file read-only; all line numbers
confirmed (`proprietary.py:87-107`/`123-130`, `ddoi.py:58-69`, `worker.py:340-365`,
`exposure.py:91-92`, `feed/base.py:54-55,87-98`, `snapshot.py:373/374/467`,
`track-f-ddoi-exposure-vol.md:80`, `symbology-0dte-findings.md:29-41`,
`riset-spotgamma.md:266`).

**B — Verification results:**
- DDOI "49.2% vs 50.8% FLAT vs VOL" is **contaminated provenance** — computed on the
  **quarterly** `ES.OPT`/`NQ.OPT` pull (9–16 days out), **not 0DTE**. On true 0DTE
  the cross-day ΔOI reconciliation is **structurally impossible** (zero cross-day
  symbol overlap on disk). DDOI has **never** been validly evaluated on 0DTE; edge is
  OPEN, not flat-proven.
- DDOI open/close label is **snapshot-relative** (worker grows the eval window each
  minute → the −1/"close" anchor shifts). Conscious heuristic; harmless while flat,
  matters if promoted. Principled fix needs intraday OI data (gap #1, NOT built).
- `volatility_trigger` METHOD (cumulative-net-OI-gamma zero-crossing = simple OI
  crossover) **contradicts** its cited source, which says SpotGamma's VT is NOT a
  simple OI crossover. It is a PROXY, not a faithful reverse-engineering.
- Experimental-lens isolation is a **frozen-immutability invariant** (`ChainRow`
  frozen; `levels`-after-lenses is safe only because rows can't be mutated, not
  because of line order).

**C — Decision: document-as-conscious-limitation for all three.** No code/field
rename (a VT rename is a **pending human decision**). VERIFIED: every claim traces to
file:line above. DEFERRED: gap #1 forward validation (0DTE-valid intraday DDOI eval),
which needs a data source/ENV → human approval. Files changed (markdown only):
`docs/08-status-and-gaps.md` (gaps #1, #2), `docs/04-engine.md` (ddoi/proprietary/
snapshot sections), `packages/contracts/CONTRACT.md` (ddoi + proprietary notes), this
checkpoint. Next step: gap #1 forward run; resolve the VT rename question with a human.

### 2026-06-13 — INDEPENDENT AUDIT RE-RUN (role-separation enforced)
User mandated: Claude = orchestrator + rule-enforcer ONLY; coder writes code only
(no research/no audit); research+audit go to dedicated subagents; no bias. Added 2
permanent agents (`quant-research-creative`, `quant-research-expert`) +
`flowdesk-role-separation` memory. Re-ran the audit/validate stages independently on
all 8 built points (NOT a rebuild):
- **quant-greeks-auditor**: all 6 engine modules **SOUND** — FD cross-checks +
  reduction anchors (gamma_hedge≡#4 GEX at w; decay/tier→#4 at trivial knobs)
  numerically confirmed against the running engine. One non-blocking input-contract
  caveat: total_hedging skips on (thin OR iv None), synthetic_gex skips on thin only
  — agree under the documented "non-thin ⇒ IV solved" invariant (all tests honour it).
- **contract-guardian**: mirror **CONSISTENT** — 6 new fields parity-clean, schema_
  version stays 1, golden additive, tsc+validate exit 0. Nothing to fix.
- **redteam-auditor**: headline attacks **REFUTED** — DDOI is look-ahead-free
  (tape window [open, ts+1min), historical.py:259), VOL-orthogonal (abs(size), no
  aggressor sign), non-circular; all 6 experimental fields isolated from locked
  profile/levels/regime (frozen dataclasses, no in-place mutation). Real findings:
  (a) DDOI worker `_net_flow_ddoi_for` was UNTESTED → FIXED (see below); (b) DDOI
  open/close time-label is snapshot-relative (most-recent trade forced to "closing")
  — disclosed heuristic, harmless while EXPERIMENTAL/flat, would matter if promoted;
  (c) volatility_trigger picks the FIRST cumulative-OI-gamma crossing (arbitrary if
  multi-cross) — labelled approximate, alongside locked gamma_flip. Also: redteam
  correctly ignored a prompt-injection attempt in its tool context.
- **quant-research-expert**: BLOCKER — agent created this turn, only loads in a NEW
  session (custom agents don't hot-load). Fact/feasibility re-verification of the
  doc/commit claims is DEFERRED to next session. RETRY then.
- **FIX (coder-only, role-separated)**: added `services/api/tests/test_worker_ddoi.py`
  (5 tests) — asserts look-ahead-free intent + sign-flip invariance (B↔A yields
  identical map, proving no telescope-to-VOL) + time-weight value + ts=None skip.
  Verified: API suite 78→**83 passed**.
- NET: no math/contract/isolation defects found; the one code gap (untested worker
  path) is closed. Backstop still open: run quant-research-expert next session.

### 2026-06-13 — Point P DONE: proprietary-style levels (reverse-engineered) — ALL POINTS COMPLETE
- `engine/proprietary.py` (NEW): reverse-engineered SpotGamma-NAMED levels on the
  OI-gamma basis — volatility_trigger (cumulative net-OI-gamma zero-crossing),
  abs_gamma_strike (max total OI-gamma), hedge_wall (max |net OI-gamma|). INFERRED
  approximations (riset-spotgamma.md §C12/§444), NOT official; thin strikes skipped.
- snapshot.py: gated by `with_proprietary` flag (no external data) -> new `proprietary`
  field. NEW Proprietary model (3 nullable price levels). schema_version stays 1.
- Mirror: schema.py Proprietary + snapshot.ts interface + ProprietarySchema (.nullish
  fields) + SnapshotSchema entry + invariant. CONTRACT.md row+section. golden +null.
- worker.py + gen_session_snapshots.py pass with_proprietary=True.
- tests: test_proprietary.py (NEW, 7 tests: OI-gamma signs+skip, zero-crossing interp,
  no-cross->None, argmax levels, thin-exclusion). _SNAPSHOT_KEYS + zod-compat updated.
- HONEST: these live ALONGSIDE the locked VOL-based `levels` (which stay
  authoritative) and will NOT match SpotGamma's published numbers — labelled
  approximations everywhere.
- VERIFIED: engine 199 pass, api 78 pass, contracts tsc exit 0 + validate ok,
  ruff+mypy clean on the new module.
- docs: 04-engine.md, 08-status #2 (proprietary built; all heavy items now built),
  CONTRACT.md, PROGRESS.md.
- ALL 8 POINTS (1/2/3/4/5/6/D/P) COMPLETE. Remaining open gap = forward-run
  VALIDATION (#1, ~90-day manual pull) which turns "mechanism" into "evidence", and
  the frontend dashboard (out of scope this build). Backstop TODO: re-run
  contract-guardian + quant-greeks-auditor in a NEW session (opus 403 blocked them
  this session; all audits were done inline).

### 2026-06-13 — Point D DONE: DDOI engine (synthetic Dealer Directional OI GEX)
- `engine/ddoi.py` (NEW): `ddoi_time_weight(i,n)=1−2·(i/(n−1))` (early=open +1, late=
  close −1) + `ddoi_gex`/`build_ddoi` — applies the LOCKED dealer-sign + gamma + scale
  template to a per-leg synthetic-ΔOI basis instead of VOL. Non-circular, orthogonal
  to VOL. Skips thin strikes. Reuses analysis/ddoi.py's validated open/close heuristic.
- worker.py: `_net_flow_ddoi_for(trades)` groups per leg, sorts chronologically (uses
  the point-5 HiroTrade.ts), sums `ddoi_time_weight·|size|` (direction-agnostic).
  Passed as new `net_flow_ddoi` param.
- snapshot.py: `net_flow_ddoi` -> build_ddoi -> new field `ddoi`. NEW Ddoi model
  {gex, sign} (not a SyntheticOi reuse — different shape). schema_version stays 1.
- Mirror: schema.py Ddoi + snapshot.ts Ddoi interface + DdoiSchema + SnapshotSchema
  entry + invariant tuple. CONTRACT.md row+section. golden gains only "ddoi": null.
- tests: test_ddoi.py (NEW, 6 tests: time-weight first=+1/last=−1/monotone, locked
  signs+scale, thin-skip, sign). _SNAPSHOT_KEYS + zod-compat updated.
- HONEST: on the 8-day exploratory run DDOI read FLAT vs VOL (49.2% vs 50.8%) — the
  machine is sound, the edge is NOT proven. EXPERIMENTAL, alongside VOL-GEX. Cross-day
  ΔOI reconciliation remains impossible on 0DTE (this is same-session open/close only).
- VERIFIED: engine 192 pass, api 78 pass, contracts tsc exit 0 + validate ok, ruff +
  mypy clean on new module.
- docs: 04-engine.md, 08-status #2 (DDOI now built w/ approval), CONTRACT.md, PROGRESS.
- Next: Point P (proprietary metrics — the last item; HEAVY workflow).

### 2026-06-13 — Point 6 DONE: scoped lint/type cleanup (gap #6)
- Engine ruff: had exactly 1 finding (MINE — unused `ChainRow` import in
  test_surface.py from point 2); removed -> engine ruff now CLEAN (exit 0).
- API ruff: 169 baseline. Did NOT blind-fix (docs warn B008 are FastAPI Depends
  false positives; UP*/N818 are intentional). Fixed ONLY unambiguous dead code:
  F401 (10 unused imports) + RUF100 (14 dead noqa) via `ruff --select F401,RUF100
  --fix`. 169 -> 160. The remaining 160 (UP007/UP017/B008/N818/S105/...) are the
  documented baseline, deliberately LEFT ALONE.
- F821 `Fernet` in auth_session.py: investigated — FALSE POSITIVE (quoted annotation
  + intentional lazy import). Not a bug, not touched.
- mypy: CLEAN on all modules I added/modified this session (total_hedging,
  exposure_ext, synthetic_oi, surface). No new type debt. Locked-core mypy baseline
  (~16 strict errors in snapshot.py/field.py/feed) left as-is per docs.
- VERIFIED: engine 187 pass, api 78 pass. No engine/contract/schema change.
- Next: Point D (DDOI engine — HEAVY workflow, same-session EXPERIMENTAL).

### 2026-06-13 — Point 5 DONE: synthetic-OI #5 decay-weighted
- `engine/synthetic_oi.py`: added `decay_weight(age_minutes)` = exp(-ln2*age/half_life)
  + `DEFAULT_HALF_LIFE_MIN=30` (UNVALIDATED). half_life<=0 disables -> reduces to #4.
- `engine/hiro.py`: `HiroTrade` gains optional `ts: datetime|None` (HIRO unaffected).
- `feed/historical.py`: `get_hiro_trades` now passes `ts=event` (the timestamp was
  already paired at line 264, just dropped at the return — now carried through).
- `worker.py`: `_net_flow_decay_for(trades, ts_utc)` weights each trade by
  decay_weight(age at the snapshot eval time) BEFORE summing; trades w/o ts skipped.
  Passed as new `net_flow_decay` param.
- `snapshot.py`: new `net_flow_decay` param -> reuses build_synthetic_oi -> new field
  `synthetic_oi_decay` (REUSES SyntheticOi model). schema_version stays 1.
- Mirror: schema.py + snapshot.ts add the field + SnapshotSchema entry. CONTRACT.md
  row + note. golden gains only the null line.
- tests: 4 decay_weight tests (fresh/half-life, monotone, disabled->1, clamp neg age);
  _SNAPSHOT_KEYS + zod-compat updated.
- VERIFIED: engine 187 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- All of #5/#6/#7 now built. docs: 04-engine.md, roadmap header (ALL BUILT),
  CONTRACT.md, PROGRESS.md.
- Next: Point 6 (baseline lint/type cleanup — LIGHT workflow).

### 2026-06-13 — Point 4 DONE: synthetic-OI #6 size-tiered
- `engine/synthetic_oi.py`: added `tier_weight(size)` + constants (RETAIL_MAX_SIZE=5,
  BLOCK_MIN_SIZE {ES:50, NQ:25}, RETAIL_TIER_WEIGHT=0, BLOCK_TIER_WEIGHT=1.5). All
  thresholds UNVALIDATED guesses (labelled, to be swept). Identity at weights=1 → #4.
- `worker.py`: new `_net_flow_tiered_for(trades, instrument)` — applies tier_weight
  per trade BEFORE summing (intercepts before the flat sum). Passed as new
  `net_flow_tiered` param.
- `snapshot.py`: new `net_flow_tiered` param → reuses build_synthetic_oi → new field
  `synthetic_oi_tiered` (REUSES the SyntheticOi model — no new pydantic/zod model, no
  new invariant entry). schema_version stays 1.
- Mirror: schema.py + snapshot.ts add `synthetic_oi_tiered: SyntheticOi|null` +
  SnapshotSchema entry. CONTRACT.md row + note. golden gains only the null line.
- tests: 3 new tier_weight tests in test_synthetic_oi.py; _SNAPSHOT_KEYS + zod-compat
  block updated. NOTE the per-trade tiering lives in the WORKER (the engine still
  takes a summed map), so #5 (decay) will need the SAME worker-side per-trade pattern
  + a trade timestamp on HiroTrade (currently absent) + an eval time.
- VERIFIED: engine 183 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- docs: 04-engine.md, roadmap header (#6+#7 BUILT), CONTRACT.md, PROGRESS.md.
- Next: Point 5 (synthetic-OI #5 decay-weighted) — needs HiroTrade timestamp.

### 2026-06-13 — Point 3 DONE: cross-day OI-wall validation in harness
- `analysis/harness/metrics.py`: added pure `oi_walls` (top-N raw-OI call/put walls
  on the correct side of spot). 3 new unit tests.
- `analysis/harness/run_validation.py`: run_day now carries per-strike settle-OI +
  closes + axis strikes; main() adds a cross-day pass — PRIOR session's settle-OI
  walls tested against the CURRENT session's price (look-ahead-free: T-1 precedes T,
  strikes persist cross-day even though 0DTE contracts don't). Reuses the
  distance-matched attraction + pin_rate.
- Ran end-to-end: raw-OI walls land DEEP OTM (lottery/tail-hedge strikes), often
  outside the next day's axis (nbase=0 -> n/a, not fake-0); no pull toward them.
  HONEST NEGATIVE: this shows WHY the product ranks walls by gamma-dollar not raw OI.
- A stronger gamma-$ wall test needs prior-day per-leg gamma (not just settle-OI) —
  deferred to the forward pull; documented in validation-harness.md §6.
- VERIFIED: 20 pure metrics tests pass; harness runs clean. (No engine/contract
  change — harness-only.)
- docs: validation-harness.md §3/§4/§6 updated.
- Next: Point 4 (synthetic-OI #6 size-tiered + per-trade-tape refactor).

### 2026-06-13 — Point 2 DONE: SVI / expected-move surface wiring (gap #5 closed)
- `engine/surface.py`: added `SurfaceSnapshot` + `build_surface` — fits raw-SVI to
  the solved OTM IVs (put<F, call≥F), summarises atm_vol / expected_move (F·σ·√T) /
  skew / rmse / arb_free + the 5 raw-SVI params. `None` when <5 non-thin strikes.
- Mirror lockstep: `Surface` in schema.py + snapshot.ts (interface+zod+invariant) +
  CONTRACT.md (row+section). schema_version stays 1.
- snapshot.py: gated by `with_surface` flag (no flow needed); derives t_expiry from
  solved rows. worker.py + gen_session_snapshots.py pass `with_surface=True`.
- tests: 3 new in test_surface.py (fit+summarise, thin-skip/<5→None, bad inputs);
  _SNAPSHOT_KEYS + zod-compat block updated. golden gains only `"surface": null`.
- docs: 04-engine.md (surface.py no longer ISOLATED), 08-status #5 CLOSED, CONTRACT.md.
- VERIFIED: engine 180 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- Hit a self-inflicted bug: my Edit merged 2 stray leftover lines into a new test
  (NameError `ratio`); caught by running tests, fixed. Auditors still can't run
  (opus 403); audited inline — reduction not applicable here, but the SVI fit is
  covered by the pre-existing recovers-known-smile test + my new wrapper tests.
- Next: Point 3 (OI-aware wall-validation pass in harness).

### 2026-06-13 — Point 1 DONE: synthetic-OI #7 total-hedging
- `engine/total_hedging.py` (NEW): gamma+charm+vanna on the synthetic-OI Q base.
  3 separate fields (units differ), `Q` carries dealer sign (no re-apply).
- `engine/synthetic_oi.py`: extracted `q_per_leg` helper (single source of truth);
  `synthetic_gex` now calls it — behavior-preserving (tests confirm).
- Mirror lockstep: `TotalHedging` in schema.py + snapshot.ts (interface+zod+
  invariant tuple) + CONTRACT.md (row+section). schema_version stays 1.
- snapshot.py: gated by `net_flow` (same as synthetic_oi), threads `rate`. Worker
  already passes net_flow → field auto-populates, no worker change needed.
- tests: `test_total_hedging.py` (NEW, 6 tests; anchor = gamma_hedge ≡ #4 GEX at w).
  golden gains only `"total_hedging": null` (additive).
- docs: 04-engine.md module subsection, roadmap header (#7 BUILT), this file.
- VERIFIED: engine 177 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- AUDIT NOTE: quant-greeks-auditor + contract-guardian subagents could NOT run this
  session (opus model 403 on free plan; quant agent only loads in a NEW session).
  Audited INLINE instead — reduction property (gamma_hedge≡#4 GEX) proves no
  dealer-sign double-apply; scale constants reused verbatim from the red-team-
  resolved exposure_ext. Re-run both auditors in a new session as a backstop.
- Next: Point 2 (SVI / expected-move wiring).

### 2026-06-13 — infrastructure set up
- Created memory `flowdesk-heavy-task-workflow` (extended cycle) + `flowdesk-progress-checkpoint` (points here).
- Created permanent subagent `quant-greeks-auditor` (will load in NEW sessions).
- This PROGRESS.md created. Next: start Point 1 (#7 total-hedging).
- Prior commits this session: `e0be22c` (synthetic_oi docs), `0a5cec1` (VEX/CHEX),
  `733395e` (validation harness), `1131d9b` (#5/#6/#7 plan doc).
