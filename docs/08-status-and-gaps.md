# 08 — Status & Gaps (the honest map)

> **CURRENCY NOTE (2026-06-22):** `schema_version` is now **2**, bumped in commit
> `2b13ae2` (the HIRO→FLUX / TRACE→FOG rename). Audit blocks below dated
> 2026-06-14 that say "schema_version stays 1 / untouched" were accurate at the
> time of those decisions (the listed changes were individually non-breaking);
> the version moved to 2 later in the rename commit. The canonical value lives in
> `schema.py` ↔ `snapshot.ts` ↔ `CONTRACT.md` (all `2`). Three additive
> EXPERIMENTAL fields landed after this doc's main body was written —
> `theta_decay`, `max_pain`, `vol_expansion` (commit `af2ef7d`), plus `iv_smile`
> (commit `2d36cd6`) — all optional/nullable, documented in `docs/04-engine.md`.

This is the document to read when the project "feels done but lacking." It is the
backlog. The backend is **code-complete and well-engineered**, but it is built on
the **methodologically weakest version of the core signal** and is
**validation-incomplete**. Both things are true at once.

## What is genuinely solid ✅

- **Deterministic, pure engine** with a golden fixture. Same inputs → same Snapshot.
- **Cross-language contract** byte-for-byte mirrored (pydantic ↔ zod), with a
  validate step that accepts the example and rejects malformed input.
- **Good test coverage** of the plumbing: 442 engine tests, 116 API tests
  (re-counted via `pytest --collect-only` on 2026-06-19), closed-form Black-76
  checks, IV convergence, exposure signs, field invariant, level extraction,
  FLUX signing, auth/entitlement/state.
- **Clean separation**: engine is calendar-free; the API owns time/state.
- **Locked design system** enforced in code via tokens.

The architecture is sound and reusable. **The verdict is REWORK, not rebuild.**
The gap is the *signal layer* and a *validation layer* — both **additive**, not a
teardown of the plumbing.

## The gaps, in priority order

### 1. Validation harness — MECHANISM built; evidence still missing 🟡→🔴
The engine computes GEX/DEX/levels whose **predictive relationship to price is
still unproven**. A first offline harness now EXISTS (`analysis/harness/`,
[`research/empirical/validation-harness.md`](research/empirical/validation-harness.md)):
- `metrics.py` — pure, unit-tested metric core (17 tests): magnitude reconciliation
  (volume-controlled partial Spearman), distance-matched level-attraction, pin rate.
- `run_validation.py` — streams the 4 correct 0DTE sessions, builds per-minute
  snapshots, feeds the metrics.

**What it does NOT do — the gap is still open:**
- It is **mechanism, not evidence**: 4 correlated sessions (one crash day). Every
  number is descriptive; the real test is the operator's ~90-day forward run, which
  calls this same code.
- **Directional ΔOI reconciliation is impossible on 0DTE** (contracts expire same
  session → zero cross-day key overlap; settle-OI is sign-definite). Only the
  **magnitude** relation is testable, and — first honest result — its raw rho (~0.4)
  **collapses to ~0.08–0.24 once volume is controlled**, i.e. the apparent
  reconciliation is mostly "active strikes are active," not positioning skill.
- **No pinning signal** is visible on the 4 days (excess-attraction small/mixed,
  pin-rate ≈ 0) — as expected at this n; not a result either way.
- The golden test still only proves **self-consistency**, not correctness.

So this stays the #1 gap until the forward run exists — but the *machine* to run it
is now built and adversarially hardened (a look-ahead bug and a distance-baseline
bias were caught and fixed in review). **DDOI / wall validation needs an OI-aware
pass and is deferred** (settle-OI at the open would be look-ahead). Note that DDOI's
**cross-day** ΔOI-reconciliation form is not merely deferred but **structurally
impossible on 0DTE** (zero cross-day symbol overlap; see Gap #2) — only a 0DTE-valid
**intraday, same-session** evaluation is even definable, and it does not yet exist.

### 2. The GEX core is the naive version 🔴 (decided, but know its limits)
`exposure.py` uses **cumulative VOL × a hardcoded static dealer sign**
(`+1` call / `-1` put). This is intentional (decision #1) and locked, but it is
the weakest methodology:
- Aggressor side ≠ customer side; a static sign cannot capture real dealer
  inventory.
- Cumulative volume double-counts round-trips and has no position decay.

A first **synthetic-OI signed-flow-update lens now exists** — `synthetic_oi.py`,
wired as the **optional, EXPERIMENTAL** `synthetic_oi` Snapshot field (OI-anchored
position updated by native aggressor flow, weight `w∈[0,1]`), plus its successors
`synthetic_oi_tiered` (#6 size-tiered), `synthetic_oi_decay` (#5 decay-weighted) and
`total_hedging` (#7 gamma+charm+vanna). A **DDOI** lens (`ddoi.py`) is **now also
built** (with explicit approval) — a non-circular open/close-classified synthetic ΔOI
GEX, wired as the optional `ddoi` field. All live **alongside** VOL-GEX, do **not**
replace it, and are **not price-validated** (synthetic-OI structural on 4 days) — so
they do **not** close gap #1.

> **AUDIT (2026-06-14, quant-greeks-auditor) — synthetic-OI family #4/#5/#6/#7:
> SOUND math, but LIVE-ONLY / ABSENT from the committed FE sessions.** Dimensions,
> signs and reductions all check out: #6 tiered reduces EXACTLY to #4 when tier
> weights = 1.0; #5 decay reduces to #4 when `half_life <= 0`; #4 with `w -> 0`
> recovers pure OI-GEX. In the LIVE worker the three flow maps ARE genuinely
> distinct (tiered drops retail at `RETAIL_TIER_WEIGHT=0.0`, block ×1.5; decay
> reweights by recency + drops ts-less trades), so #5/#6 do NOT collapse to #4 in
> live. **FACT:** the whole family is computed ONLY in the live worker
> (`worker.py:394-397` passes `net_flow`/`net_flow_tiered`/`net_flow_decay`/
> `net_flow_ddoi`); the offline generator `gen_session_snapshots.py:113-118` passes
> **none** of them, so `synthetic_oi`/`_tiered`/`_decay`/`total_hedging`/`ddoi` are
> **ABSENT from the committed FE session JSON** — the FE renders these only off a
> live worker, never off the checked-in sessions. **#7 `gamma_hedge` == #4 `gex`
> bit-for-bit** (documented; only `charm_hedge`/`vanna_hedge` are novel).
> **RESIDUAL RESOLVED (2026-06-14) — the window IS cumulative-since-RTH-open,
> NOT per-minute.** FACT (read-only, the-advisor + coder): the worker's
> `_fetch_signed_trades` delegates to `feed.get_flux_trades`, whose window is
> `[rth_open, ts+1min)` — `historical.py:229-260` filters every tape event with
> `if event < rth_open or event >= end: continue` and the docstring states "over
> the RTH window `[open, ts]`". So the synthetic-OI flow maps (and FLUX, and the
> #5 decay-age math) all accumulate over the same cumulative-since-open basis the
> docs already describe. The residual is **closed** (confirmed behaviour, not a
> bug).
>
> **SECOND PARITY GAP — synthetic-OI absent from FE JSON is DEFERRED (couples to
> Gap #4).** The FACT above (worker computes `net_flow*`, the offline generator at
> `gen_session_snapshots.py:113-118` passes only `ohlc`/`flux`) is the **same
> worker/generator divergence class** as the FLUX defect in Gap #4 — a second,
> knowingly-left parity gap. **DEFER rationale:** wiring `gen_session_snapshots`
> to emit `net_flow`/`net_flow_tiered`/`net_flow_decay` only matters once the
> dashboard renders these lenses, which is the Gap #4 decision — no point
> generating data the FE does not yet draw. **When Gap #4 is built:** wire the
> generator to pass the `net_flow*` maps for whichever lenses the dashboard shows.
> Stays DEFERRED, not done.

> **UPDATE (2026-06-14) — synthetic-OI #4 FLOW TERM now has a 0DTE-valid SAME-SESSION
> STRUCTURAL eval; BOTH /ES and /NQ = UNDETERMINED at n=4.**
> `analysis/harness/synthetic_oi_eval.py` (+ runner + **16 tests**; full harness suite
> = **74 pass**, run through the tenor-provenance guard) tests the ONE thing
> synthetic-OI #4 uniquely claims over a classic OI-GEX vendor. **the-advisor
> corrected the axis:** NOT "synthetic vs VOL" (that is CONFOUNDED — it mixes the
> locked OI-vs-VOL basis decision #1 with the flow term) but **`gex` (w=1) vs
> `gex_static` (w=0)** — does the native-aggressor FLOW term `(−flow)·w` add per-strike
> STRUCTURE OVER pure OI-GEX? **This arm as built is STRUCTURAL, NOT predictive — there
> is NO hit-rate / NO "55%"**: this runner scores nothing against price and anchors on
> same-day settle OI. **CORRECTION (2026-06-14) — a *predictive* arm is UNDERPOWERED
> (n=4), NOT "blocked".** An earlier version here said a predictive arm is "BLOCKED
> because synthetic `Q` needs prior-session `OI_open` … 0DTE has zero cross-day overlap"
> — that **conflated two things and is wrong.** FACTS (research-expert, session-verified,
> decoded this session): (1) there is **no real-time OI feed** (exchanges publish OI once
> daily at settle) — that is the *reason* synthetic-OI exists (it reconstructs intraday
> positioning from real-time signed FLOW + an OI anchor); (2) synthetic-OI's method is
> **t-causal** (`Q = anchor_OI + cumulative_signed_flow(≤t)`, `synthetic_oi.py:139-141`);
> (3) a clean **prior-session OI anchor DOES exist on disk** — `stat_type 9` stamped
> `ts_ref = D-1` inside each day-D file, observable **pre-open** (~02:00 UTC), non-zero
> for the day's expiring iids (decoded counts 1133 / —post-open / 1080 / 1187); this does
> NOT contradict the "zero cross-day symbol overlap" finding (that is about which
> *contracts trade* 0DTE, not where the anchor lives); (4) the only real look-ahead was a
> **harness choice** (this runner grabs the latest `stat9` = same-day settle), and on
> this data its realized contamination is ~zero (latest `stat9` IS the `ts_ref=D-1` value
> for 3/4 days). **So a t-causal predictive synthetic-OI eval is RUNNABLE look-ahead-free
> on existing data — UNDERPOWERED (n=4), not blocked — but UNBUILT, pending a decision to
> build a regime-kernel eval vs gather more data.** INFERENCE (advisor): synthetic-OI/GEX
> is a **volatility-regime** predictor (net-GEX sign → dealer gamma posture), NOT a
> directional up/down predictor — a predictive eval must score a vol/mean-reversion
> outcome, NOT `sign(return)`, and a flow-only arm would ~duplicate the already-null FLUX
> directional eval; the new content is the **prior-OI-anchored regime predictor**.
> **AGGREGATOR ANCHOR verified
> (load-bearing):** the new sign-free `synthetic_gex_by_strike` sums EXACTLY to the
> engine's scalar `synthetic_gex` at w=0/0.5/1.0 (`math.isclose`), and does NOT
> re-apply the dealer sign already baked into `Q` (the double-sign trap was AVOIDED —
> a NEW aggregator, not `ddoi_divergence.gex_by_strike`). Metrics: `residual_r2`
> (rescale-null), `flow_norm_ratio` (headline magnitude), `argmax_distance`, vs a
> shuffled-aggressor-sign null; the DDOI `Σw=0` sign-flip detectors were deliberately
> NOT used (wrong mechanism). **RESULT (per-instrument, never pooled):** the flow term
> is **materially-sized** (mean `flow_norm_ratio` ~0.5 /ES, ~0.79 /NQ) but its
> DIRECTION is **NOT separable** from random-sign flow at n=4. **/ES UNDETERMINED**
> (mean `norm_ratio_gap` +0.030 < 0.05, per-day sign 1+/3− inconsistent). **/NQ
> UNDETERMINED** — a prior "YES (exploratory)" was a **single-day artefact** (06-05's
> +1.017 is ~245% of the signed sum; excluding it the mean is −0.201; sign 2+/2−
> inconsistent); the **red-team caught it** and the verdict logic was fixed to require
> per-day sign consistency (mirroring the FLUX pooling defect class), so **NQ now reads
> UNDETERMINED, never YES.** **Verdict: NOT a demonstrated edge, NOT a demonstrated
> absence.** **#4 and #6 are now both evaluated.** **#6 SIZE-TIERED arm (added
> 2026-06-14, code `23fdbfa`):** tests whether size-tiering the flow adds per-strike
> structure **OVER the plain #4 flow term** (reference = plain #4, NOT pure OI);
> `tier_weight` is IMPORTED from the engine and a reduction test proves tiered == plain
> when all tier weights = 1.0. **RESULT: UNDETERMINED at n=4** — tiering is a
> **near-scalar-rescale** of the plain flow term (`residual_r2` 0.85–0.998) and **every**
> day-instrument `norm_ratio_gap` is **NEGATIVE** (no added directional structure over
> plain flow); the engine default `retail_weight=0.0` **DELETES ~80% of trades** (ES ~19%
> / NQ ~21% survive). The `MIN_DAYS_FOR_EDGE=5` gate makes YES unreachable at n=4 for
> both arms. **81 harness tests pass.** Still **DEFERRED: #5 decay** (needs a new decay
> flow-map construction) and **#7 `charm_hedge`/`vanna_hedge`** (its `gamma_hedge` == #4
> `gex` bit-for-bit); also DEFERRED a **t-causal predictive eval** (runnable
> look-ahead-free, underpowered n=4 — see the correction above, UNBUILT). The
> synthetic-OI family is still **ABSENT from committed FE session
 > JSON** (live-only, as above). Still EXPERIMENTAL, still not price-validated; see
> [`research/empirical/synthetic-oi-eval.md`](research/empirical/synthetic-oi-eval.md).

> **UPDATE (2026-06-14) — the t-causal PREDICTIVE synthetic-OI eval is now BUILT
> (look-ahead-free), reads UNDETERMINED at n=3; the remaining gap is POWER, not
> method.** The eval flagged "UNBUILT, runnable look-ahead-free, underpowered" above
> now EXISTS: `analysis/harness/synthetic_oi_regime_eval.py` (pure core) +
> `run_synthetic_oi_regime_eval.py` (runner) + 2 test files; **109 harness tests
> pass**, run through the tenor-provenance guard. It scores synthetic-OI as a
> **VOLATILITY-REGIME** predictor (NOT directional — the FLUX directional kernel was
> deliberately NOT reused): predictor = per-minute `sign(Σ synthetic-GEX)` from
> `Q = prior-session-OI-anchor + cumulative_signed_flow(≤t)` (long-gamma=+ ⇒
> vol-suppression; short-gamma=− ⇒ vol-amplification); outcome = the SIGN-FREE move
> `|F_{t+k}−F_t|` (k=5/15/30); metric `sep_k` vs a regime-label-shuffle null (HEADLINE)
> + aggressor-sign-shuffle + flow-only(anchor=0) controls. **Look-ahead-free by
> construction:** the OI anchor is the `stat_type-9` quantity at MAX `ts_recv` subject
> to `ts_recv < RTH open` (13:30 UTC) — never relaxed (the intraday OI republish shares
> the same `ts_ref`, only `ts_recv` separates them); `ts_ref` must be a PRIOR session
> (fail-closed). A **red-team caught one residual leak** (cum-flow at minute `t`
> included minute-`t` trades after `F_t`); **FIXED** (snapshot-before-fold,
> `out[0] == {}`), the null held UNCHANGED (the leak was masked at n=3, not creating a
> false signal), and 2 tests now encode the anti-leak guarantee. **HARD LIMITS:** only
> 4 0DTE days on disk; **06-08 DROPPED** (no pre-open OI publish, only an intraday
> ~14:11 UTC republish ⇒ using it would be look-ahead) → **n=3 usable**
> (06-05/09/10); ES gamma-dense (~360–379 solvable min), NQ sparse (~103–171); **06-05
> has no regime flip** (all short-gamma) ⇒ zero within-day separation. **RESULT: BOTH
> /ES and /NQ UNDETERMINED at every k** (sign-inconsistent / single-day-dominated;
> `MIN_DAYS_FOR_EDGE=5` makes YES unreachable). The metric is **proven ALIVE**
> (planted positive control). **VERDICT: UNDETERMINED at n=3 — NOT shown, NOT
> refuted.** This is the honest expected outcome at this n; the eval is correct,
> look-ahead-free, and a **reusable template**. The **only blocker to a real verdict is
> statistical power (more independent days)** — NOT method, and NOT a real-time OI feed
> (there is none; synthetic-OI exists precisely because OI publishes once daily at
> settle — predictive is RUNNABLE look-ahead-free from a prior-session anchor + intraday
> flow, just UNDERPOWERED). The user dropped the data pull that would power it. Still
> EXPERIMENTAL, still not price-validated; see
> [`research/empirical/synthetic-oi-predictive-eval.md`](research/empirical/synthetic-oi-predictive-eval.md).

> **HONESTY FIX — the DDOI "49.2% vs 50.8% FLAT vs VOL" number is contaminated
> provenance and must NOT be cited as a 0DTE result.** That figure
> (`research/empirical/track-f-ddoi-exposure-vol.md:80`, self-labelled "8-day
> EXPLORATORY — descriptive, NOT validated") was computed on the **quarterly**
> `ES.OPT`/`NQ.OPT` parent pull (multi-expiry, 9–16 days out), **not 0DTE** — see
> `research/empirical/symbology-0dte-findings.md:29-41`. On **true 0DTE**, the
> cross-day ΔOI reconciliation DDOI relies on is **structurally impossible**: every
> consecutive day pair has **zero** overlapping option roots (each day is its own
> daily expiry — verified on disk from `data/raw/zerodte/symbols_by_day.json`). So
> **DDOI has never been evaluated on valid 0DTE data, and its cross-day ΔOI-
> reconciliation form cannot be on 0DTE.** Whether DDOI carries a measurable edge
> under a **0DTE-valid (intraday, same-session)** evaluation is **OPEN and
> unanswered** — part of the gap #1 forward-validation roadmap, not a closed result.

> **UPDATE — a 0DTE-valid SAME-SESSION structural eval now exists; first result is
> INCONCLUSIVE-leaning-redundant.** `analysis/harness/ddoi_divergence.py` (+ runner +
> 14 tests, run through the tenor-provenance guard) compares the DDOI-GEX vs VOL-GEX
> per-strike profiles at end-of-session on the 4 real 0DTE days. It is a
> **structural-divergence check, NOT predictive** (the time weight `w(i)=1−2·i/(n−1)`
> is whole-day-normalized, so per-minute predictive use would be look-ahead — out of
> scope). Key mechanism: `Σ w(i) = 0`, so `ddoi_leg = Σ w(i)·|size|` is a **de-meaned
> volume timing-skew** statistic, not a contracts-outstanding ΔOI; back-loaded
> dominant legs make DDOI-GEX ≈ **−c·VOL-GEX** (same strikes, flipped sign). On n=4
> (descriptive, incl. a crash arc) the signed correlation (≈ −0.34) is **mostly that
> mechanical sign-flip + noise** — bimodal (2/8 rows textbook sign-flip-redundant,
> the rest low-magnitude). **Verdict: INCONCLUSIVE-leaning-redundant — DDOI is NOT
> shown to add information over VOL-GEX**, and the auditors advised NOT funding the
> ~90-day predictive run on it. Still EXPERIMENTAL, still not price-validated; see
> [`research/empirical/ddoi-structural-eval.md`](research/empirical/ddoi-structural-eval.md).
**Do not rip out VOL-GEX.** When the forward-run validation (#1) exists, all these
become parallel, measurable layers to rank against VOL-GEX. The **proprietary
metrics** (Volatility Trigger / Absolute Gamma / Hedge Wall) are **now also built**
(`proprietary.py`, optional `proprietary` field) — but as **reverse-engineered
approximations on the OI-gamma basis, NOT official SpotGamma values**, living
alongside the locked VOL-based `levels`.

> **HONESTY FIX — `volatility_trigger`'s METHOD contradicts its cited source.** The
> code (`proprietary.py:87-107`) computes the Volatility Trigger as the **cumulative
> net-OI-gamma zero-crossing — a simple OI crossover**. The cited research
> (`research/archive/riset-spotgamma.md:266`, also :444) states SpotGamma's
> Volatility Trigger is **[PROPRIETARY] … from the actual distribution of dealer
> gamma across strikes, NOT a simple OI crossover.** So the implemented method
> **directly contradicts** the documented description of the real metric: it is a
> tractable **PROXY**, not a faithful reverse-engineering. (`hedge_wall`,
> `proprietary.py:123-130`, argmax `|net OI-gamma|`, likewise diverges from the
> doc's argmax `|total gamma|` near-spot hypothesis, `mega-riset2.md:157`;
> `abs_gamma_strike` DOES match the doc's [FAKTA] argmax-total-gamma definition.)
> The existing EXPERIMENTAL/INFERRED labels are honest; the new caveat is only that
> VT's OI-crossover method is the wrong *mechanism* for the named level. **Whether to
> rename the field is a pending HUMAN decision — no code/field rename here.** The Fase
> 2 dissection sharpens this: VT-as-coded is a **relabeled OI-basis gamma-flip**
> (algorithmically identical to `levels.gamma_flip`, only the basis differs), the
> archive specifies no reproducible VT formula, and FlowDesk's ES/GLBX universe has no
> validation target for one — so **no faithful VT is buildable**; building is declined
> (deferred to the gap-#1 90-day harness, never tuned to vendor numbers), and the
> rename remains a pending human decision.
>
> **UPDATE (2026-06-14) — the rename is now EXECUTED.** `volatility_trigger` ->
> `oi_gamma_flip` is committed (`e022fd7`); the field across `proprietary.py`,
> `schema.py`, `snapshot.ts`, `CONTRACT.md`, tests + golden now reads `oi_gamma_flip`,
> honestly naming the method (a gamma flip on the OI basis, NOT SpotGamma's VT).
> the-advisor first-run flagged a PHANTOM `schema_version` HOLD on this: the rename is
> a key-string change with **no wire/shape change**, contract-guardian verdict
> **CONSISTENT**, so `schema_version` stays **1** (non-breaking). The τ-concentration
> "faithful VT" stays declined/deferred to the gap-#1 harness as above.
>
> **UPDATE (2026-06-14) — the "is VT more than an OI crossover?" question is now
> CLOSED with a data-backed NEGATIVE; no gamma-concentration level is built.** A
> role-separated investigation (creative + research-expert design → ONE parameter-free
> candidate → a research-expert read-only DISTINCTNESS GATE on the 4 on-disk 0DTE days
> × ES/NQ = 8 cells, decoded through the `assert_session_iids_0dte` tenor guard) asked
> whether a faithful, *local-positive-gamma-distribution* VT — the real SpotGamma
> description — is worth building as a new EXPERIMENTAL field.
> - **FACT — the user's intuition was correct.** SpotGamma's VT is a LOCAL
>   positive-gamma-*distribution* object ("konsentrasi gamma positif … last major level
>   of positive gamma support", explicitly NOT a simple crossover;
>   `mega-riset2.md:114-116`), and FlowDesk's five existing levels — `oi_gamma_flip`,
>   `abs_gamma_strike`, `hedge_wall`, call/put wall — all MISS that shape (they are
>   global argmax or cumulative zero-cross). So "`oi_gamma_flip` is just an OI
>   crossover, not VT" is a FAIR criticism: the OI-crossover genuinely is NOT the VT
>   shape.
> - **FACT — a faithful VT is still not buildable honestly.** VT's defining
>   "major/last" qualifier is a threshold τ that can ONLY be set by matching
>   SpotGamma's published SPX numbers (`mega-riset2.md:130`, H-B2 conf 55%, "τ perlu
>   kalibrasi"), which FlowDesk's /ES-GLBX universe cannot obtain. Calibrating τ to
>   vendor numbers is inference-dressed-as-reproduction — the documented catastrophic
>   failure mode (`reference/methodology-decisions.md`). A faithful VT stays declined.
> - **The ONE parameter-free, archive-grounded candidate (C-5):**
>   `VT_exp = argmax over K<F with net_oi_gamma(K)>0 of net_oi_gamma(K)` — the strongest
>   dealer-long-gamma strike below the forward. It needs no τ, so it is the only
>   honestly-buildable approximation worth gating.
> - **GATE RESULT: FAIL (read-only, session-verified on the 4 days).** C-5 is
>   **UNDEFINED (None) on 6 of 8 cells** — there is usually NO positive-net-gamma strike
>   below the forward. On the 2 computable cells it is degenerate: **06-08 NQ (29600)
>   collapses onto BOTH `hedge_wall` AND `abs_gamma_strike` simultaneously** (a relabel,
>   not a new level); **06-05 ES (7380) is ordinally broken** — it sits BELOW its own
>   `put_wall` (7400), violating the expected `put_wall <= VT <= oi_gamma_flip < F`
>   ordering. Zero cells are ordinally sane; placement is jumpy (F−C5 distance 1.3 vs
>   5.8 strike-steps across the two cells). It is not a stable level.
> - **INFERENCE (high) — structural reason.** Black-76 gamma is ~symmetric per strike,
>   so `net_oi_gamma(K) ~ g(K)·(OI_call − OI_put)`; a positive value strictly below F
>   requires call-OI > put-OI below the forward, which is rare (the downside is
>   put-OI-dominated). So C-5 fires only on a stray call-heavy strike — an artefact, not
>   a level.
> - **DECISION: DO NOT BUILD any gamma-concentration / VT-like level (option a,
>   data-backed).** C-5 is WORSE than the `oi_gamma_flip` relabel (mostly nonexistent +
>   jumpy + collapses/ordinally-broken where it exists), not better. `oi_gamma_flip`
>   keeps its honest name. No code was written. The do-not-build decision rests on the
>   distinctness-gate FAILURE alone (C-5 is an artefact, not a level); the predictive
>   question is therefore moot. (A predictive arm would be UNDERPOWERED at n=4, not
>   blocked — same corrected status as synthetic-OI, §gap-2 — but it is irrelevant here
>   because the level itself failed the gate.) The VT investigation is CLOSED with a
>   NOT-VALIDATED, data-backed negative.

With these, every heavy item on the
original backlog is built (all EXPERIMENTAL); what remains is the forward-run
**validation** that would move any of them from "mechanism" to "evidence".

### 3. Live feed — RESOLVED (Phase 3, 2026-06-15) ✅
**Was:** `feed/live.py` raised `LiveFeedNotAvailable`; only historical
replay worked.

**Now:** `feed/live.py` is a real adapter (`LiveAdapter`) gated by an
explicit two-key arming rail (`FEED_MODE=live` **and** `LIVE_FEED_ARMED=1`)
to defend against the F1–F7 failure modes catalogued in
`docs/architecture/live-feed-threat-model.md`. Highlights:

- `make_adapter("live")` refuses with `LiveFeedNotArmed` unless the
  arming key is set — neither `FEED_MODE=live` alone nor an inherited env
  can flip the worker into real-account contact.
- `import databento` is lazy and gated: it only runs inside
  `_open_client()`, behind the arming check, behind the `client_factory`
  test seam. Tests substitute a hand-rolled `FakeLiveClient` and never
  load the real package.
- Circuit breaker (`_BreakerState`): >= 5 consecutive failures within a
  rolling 5-minute window opens it permanently for the process lifetime;
  subsequent calls raise `LiveFeedDegraded`. No automatic recovery —
  humans only (F6).
- Bounded reconnect: max 5 attempts per `_connect()`, exponential
  backoff capped at 60s, 5-minute total wall budget.
- `build_worker_from_env` logs a loud WARNING with `feed_mode` /
  `live_armed` at boot so an operator can spot a misconfigured live flip
  in stdout's first line.
- Public surface (`get_chain` / `get_forward` / `get_flux_trades`) is
  shape-identical to `HistoricalSimAdapter`, so the engine, datastore,
  and locked Snapshot contract stay byte-for-byte unchanged when the
  mode flips.

**Test status:** 13 dedicated `test_live_adapter.py` tests + 23
`test_live_book.py` tests covering the assembly + shape-/refusal-coverage
tests in `test_historical.py`. **No code path in CI ever imports the real
`databento` package.**

**Minute-assembly is now BUILT (update 2026-06-18).** The deferred assembly
logic shipped: `engine/feed/live_book.py` (`LiveBook`) is a pure, network-free
per-minute assembler — 0DTE expiry selection, cumulative VOL since RTH open,
latest OI, put-call-parity / front-future forward, and the signed FLUX tape —
mirroring `HistoricalSimAdapter` byte-for-byte. The `_DatabentoLiveClient` shell
in `live.py` seeds today's definitions once via a bounded Historical HTTP pull
(a live stream does NOT resend definitions for instruments listed before the
subscription opens), then routes definition/statistics/trades/quote records into
the book. The DBN wire-format mapping is taken from the spec + the project's
`convert_dbn_to_csv.py` and is marked provisional until an operator validates it
through the runbook.

**Remaining (deferred, not on the critical path):**

- **`LiveAdapter.get_ohlc` is missing** — the worker (`worker.py:522`) calls it,
  but only `HistoricalSimAdapter` implements it, so live candle (`ohlc`) data
  silently degrades to `None`. Everything else (GEX/DEX/VEX/FLUX/levels/surface)
  computes fine on live. Fix: assemble a 1-minute OHLC from the book's
  `_fut_trades` front-future series.
- Crash-loop detector via on-disk arm-attempts log is documented in §5
  of the threat model but not yet implemented (lower priority — the
  in-process breaker + the explicit second key already cover the
  Kubernetes-restart-storm case at the orchestrator level).

Commits: `dca4e9f` (threat model) → `37e7a03` (adapter + breaker) →
`c46cb20` (refuse-by-default rail) → `69d7893` (mocked tests).

### 4. Frontend — DELETED 2026-06-15 (pending redesign) 🟡
The original frontend (`apps/web/`, `@flowdesk/tokens`, all heatmap/profile/FLUX/
auth components) was deleted on 2026-06-15 to be rebuilt from scratch. Locked
design rules (TURQUOISE/CRIMSON, Space Grotesk + JetBrains Mono) remain in
`02-locked-contract.md` and any future FE must honor them. See PROGRESS.md
2026-06-15 checkpoint.

The FLUX-related backend findings below remain valid (they are about
`engine/flux.py` and the worker, not about the deleted FE):

> **AUDIT (2026-06-14, quant-greeks-auditor) — FLUX: DOWNGRADE (consistency
> defect, NOT look-ahead). MUST fix before the FE renders FLUX.** `flux.py` is
> dimensionally sound (greek-weighted dealer delta-notional USD, properly delta-
> dollarized `×M×F`), the aggressor sign `B/A/N -> +1/-1/0` is correct with no
> double-sign, and it is **strictly t-causal** — window `[rth_open, ts+60s)`, real
> daily reset, per-trade `ts` threaded, **no look-ahead**. THE DEFECT: the live
> worker (`worker.py:264`) **re-prices the entire day's tape at the single current
> forward `F_t` every minute**, so cumulative FLUX drifts even on zero-trade minutes
> and **DIVERGES** from the offline generator (`gen_session_snapshots.py:75-112`),
> which **freezes each trade's increment at its arrival-minute forward** via a
> persistent `FluxState`. Result: the worker and the generator render **DIFFERENT
> FLUX lines for the same session**. **FIX (record, do not perform):** unify
> accumulation — the worker should also use a persistent `FluxState` fed only NEW
> trades at each trade's arrival forward, so the line is stable + identical across
> both paths. This is a prerequisite before the FE renders FLUX.
>
> **STATUS (2026-06-15) — RESOLVED.** Phase 2 Item 3 implementation landed in
> commits `604bad5` (design doc), `445e019` (engine), `4b97756` (api worker),
> `8097228` (parity test). The api-layer worker now holds a persistent
> per-instrument `FluxState` and feeds only the NEW suffix of trades each minute
> at that minute's forward — economically correct (hedging happens at the price
> prevailing then) and BIT-IDENTICAL to `gen_session_snapshots.py:75-112` per
> the parity test (`services/api/tests/test_hiro_parity.py`, asserts ≤1e-9 abs
> diff per minute on a 6-minute scripted session including zero-trade
> minutes). Restart safety is provided by a two-tier scheme — Tier 1 reseeds
> from a Redis dump (`flowdesk:flux:{instrument}`, TTL 90m, written each LIVE
> tick); Tier 2 falls back to a fresh accumulator on any miss / wrong date /
> malformed payload / Redis hiccup. Daily reset is keyed off the ET session
> date; defensive shrunken-window detection guards against fixture rebuilds.
> Engine purity preserved: `FluxState.to_dict/from_dict` are plain scalars and
> `FluxState` is never pushed into `build_snapshot`. Snapshot contract bytes
> unchanged (no mirror-trio change). The originally-proposed `degraded` flag
> from `docs/architecture/flux-unification.md` §4.5 was descoped — it would
> touch the locked Snapshot contract and the existing WARNING log on feed
> gaps already provides the operational signal until a UX layer needs it.
> Design lives in `docs/architecture/flux-unification.md`. Full historical
> context (the original DEFERRED rationale and the advisor's design
> direction) preserved below for traceability.
>
> **STATUS (2026-06-14) — DEFERRED with design direction (advisor-revised).** FACT
> + the-advisor reasoning: the divergence is **NOT an accumulation-method bug** —
> both paths accumulate the same trade set `[open, ts]` (residual confirmed in Gap
> #2). The real gap is the **forward used per trade**: the live worker
> (`worker.py:264`) re-prices the entire day's tape at the single current-minute
> forward `F_t`, while the generator (`gen_session_snapshots.py:75-112`) freezes
> each trade's increment at its arrival-minute forward via a persistent
> `FluxState`. The generator's **frozen-increment** semantics is the
> economically-correct one (hedging happens at the price prevailing then). **DEFER
> rationale:** FLUX's only consumer is the FE render, which is **not** being built
> now (this gap); and the naive "make the worker persistent" fix would TRADE a
> cosmetic numeric-parity bug for a **restart-correctness bug** — the current
> stateless rebuild-from-`[open, ts]` is restart-safe and gap/STALE-safe by
> construction (`worker.py:203-208`), whereas a persistent `FluxState` needs
> explicit reset-at-RTH-open, mid-session-restart recovery, and feed-gap handling
> the worker does not have today. **DESIGN DIRECTION (record for when this gap is
> built):** keep the accumulator in the api-layer worker (NEVER push `FluxState`
> into `build_snapshot` — engine purity is locked); feed only NEW trades at each
> minute's forward; design the reset/restart/gap behaviour explicitly; lock
> both-paths-equal with an independent test. Before that fix, grep the golden
> fixture + worker tests for pinned FLUX values (a worker change will legitimately
> move `.final` on every minute after the first). Stays DEFERRED, not fixed.
>
> **UPDATE (2026-06-14) — FLUX now HAS a 0DTE-valid, look-ahead-free PREDICTIVE
> eval; result is exploratory null / underpowered-hint, NOT an edge.**
> `analysis/harness/flux_eval.py` (+ runner + 8 tests; full harness suite = 58
> pass) scores `sign(delta_hiro_t)` against `sign(F_{t+k}−F_t)`. Unlike DDOI, this
> is **legitimately predictive**: FLUX is strictly t-causal
> (`Σ_{trades≤t} sign·δ·size·M·F`), so the predictor (`≤t`) and outcome (`>t`)
> information sets never overlap — no whole-day normalization to contaminate it.
> The headline is the CONTROL GAP `real − mean(shuffled-aggressor-sign)`, never the
> raw hit-rate. **HARNESS PROVEN ALIVE** (planted positive control → hit_rate 1.0;
> anti-correlated → 0.0), so the near-0.5 real result is a genuine "no strong edge",
> not a dead metric. **Per-instrument three-state result** (after a red-team
> aggregation fix — pooling ES+NQ had masked the signal): **k=15/30 = NULL** on
> adequate-coverage ES (sign inconsistent across days, n-wtd gap ~+0.01/~0); **k=5
> ES = SUGGESTIVE-POSITIVE but AT-THRESHOLD + UNDERPOWERED** (4/4 ES days positive,
> n-wtd gap ~+0.047, band ~[+0.03,+0.06], fwd_cov 0.99, but n_days=4 < 5 → NOT an
> edge); **k=5 NQ = UNDETERMINED** (forward coverage as low as 0.43, too low to
> resolve). **Verdict: NOT a demonstrated edge, NOT a demonstrated absence.** The
> forward is an OPTION-DERIVED parity forward (NOT a futures price); only
> k∈{5,15,30}min tested; the ~90-day forward run was dropped by the user, so this
> stays exploratory. The live-worker FLUX accumulation fix above is **now
> RESOLVED** (Phase 2 Item 3, 2026-06-15) — see the RESOLVED block at the top
> of this gap. This predictive eval still runs on the offline/generator path,
> but the worker line is now bit-identical so the same conclusions apply
> end-to-end. See
> [`research/empirical/flux-predictive-eval.md`](research/empirical/flux-predictive-eval.md).

### 5. Surface / vanna / charm — WIRED ✅ (EXPERIMENTAL)
`black76` vanna/charm and `surface.py` are no longer isolated — all are now
**aggregated into the Snapshot** as optional, **EXPERIMENTAL** fields:
- `exposure_ext` (VEX/CHEX, `engine.exposure_ext`) — vanna/charm on the VOL basis +
  locked dealer signs.
- `total_hedging` (`engine.total_hedging`) — gamma+charm+vanna on the synthetic-OI
  `Q` base (#7).
- `surface` (`engine.surface`) — raw-SVI slice + ATM vol + **expected move** + skew.

All gated by explicit flags (`with_exposure_ext` / `with_surface` / the `net_flow`
gate), passed `True` by the worker + session generator. They are structurally built
and FD-validated at the greek level, but **not price-validated** — they do **not**
close gap #1. The remaining isolated piece is gone; this gap is closed (additive,
no contract change).

> **AUDIT (2026-06-14, quant-greeks-auditor) — VEX/CHEX: SOUND.** Dimensions correct
> (vanna/charm take ONE `F`, not `F²`; VEX's `0.01` is a vol-point / per-1%-IV scale,
> correctly NOT conflated with GEX's price-move `0.01`; CHEX's `1/365` per-day is
> correct). Signs match `black76` (vanna call == put, charm call != put). FD tests
> exist and pass (71 passed). Thin strikes skipped. Additive/optional,
> `schema_version` untouched. **ONLY caveat (already labelled EXPERIMENTAL):** the
> sign->regime "stabilising/destabilising" SEMANTICS reuse GEX's color meaning — an
> assertion only the ~90-day forward run (gap #1) can back. The FE MUST show the
> EXPERIMENTAL caveat and MUST NOT let VEX/CHEX drive the regime classifier.

> **AUDIT (2026-06-14, quant-greeks-auditor) — surface.py: DOWNGRADE (`arb_free` is
> an OVERCLAIM). The "isolated" note above is CORRECT-as-updated: surface IS wired
> (`with_surface=True` at `worker.py:399` + `gen_session_snapshots.py:116`).**
> Expected-move is dimensionally sound (`F·σ·sqrt(T)`, `T` cancels cleanly on 0DTE,
> no blow-up); thin/degenerate slices return `None` (never fabricated). THE
> DOWNGRADE: `is_butterfly_arbitrage_free` (`surface.py:130-145`) only tests
> `w(k) >= 0` (non-negative implied variance), NOT the butterfly/density condition
> `g(k) >= 0` — yet it is NAMED and documented as a no-butterfly certificate, and the
> promised `g(k) >= 0` density check (advertised at `surface.py:28`) **does not
> exist** (not in `__all__`, no implementation). So a 0DTE slice with steep
> `b·(1+|ρ|)` can pass `arb_free=True` while still carrying butterfly arbitrage.
> `arb_free` is **weaker than its name**. **FIX OPTIONS (record, do not perform):**
> implement the Durrleman `g(k) >= 0` density check, OR rename the flag to
> `variance_nonneg` and downgrade the docstring/schema wording. Until then treat
> `arb_free` as "implied variance is non-negative," not "no butterfly arbitrage."
>
> **RESOLVED (2026-06-14) — renamed `arb_free` -> `variance_nonneg`; false g(k)
> promise removed. Commit `d4f24e8`.** FACT (coder + contract-guardian): the flag
> is renamed across the mirror (`surface.py`, `schema.py`, `snapshot.ts`,
> `CONTRACT.md`, tests) and now honestly scopes to `w(k) >= 0` only; the docstring
> promise of a separate `g(k) >= 0` density check was deleted (Durrleman
> `g(k) >= 0` deliberately **NOT** implemented — the lens is unvalidated, do not
> gold-plate). **NON-BREAKING:** required sub-key inside the optional EXPERIMENTAL
> Surface block, `schema_version` stays **1**; no committed fixture carried
> `arb_free`, so zero regen / zero data pull. contract-guardian: **MIRROR
> CONSISTENT** (10/10 Surface fields parity); engine 199 pass, tsc + validate
> clean. This closes the honesty defect — it did **not** add a butterfly
> certificate (none is claimed now).

### 6. Baseline lint/type noise 🟡
Pre-existing, not blocking, do not blind-fix:
- engine `mypy -p engine`: ~16 strict errors in locked core (`snapshot.py`,
  `field.py`, `feed/__init__.py`).
- api `ruff`: ~150 mostly-stylistic findings (`UP`, `N818`, `B008` false
  positives on FastAPI `Depends`).
Scope any cleanup as its own task and re-run the golden + T-gate afterward.

## The 5 methodology divergences (all decided 2026-06-12, executed)

See `reference/methodology-decisions.md` for full rationale.

| # | Topic | Decision | Built? |
|---|---|---|---|
| 1 | GEX basis | VOL-based, cumulative | ✅ (DDOI alternative ❌, deferred v3) |
| 2 | Walls | gamma-dollar Top-3 | ✅ |
| 3 | Day-count | real wall-clock to 16:00 ET | ✅ |
| 4 | FLUX source | `trades.side` aggressor | ✅ |
| 5 | FLUX in Snapshot | optional field, no version bump | ✅ |

## One-line summary

> The skeleton, muscles, and skin are excellent. What's thin is the **nervous
> system** (a signal proven to mean something) and the **mirror** (a way to check
> it against reality). Build the validation harness next; everything else is
> additive polish on a solid frame.
