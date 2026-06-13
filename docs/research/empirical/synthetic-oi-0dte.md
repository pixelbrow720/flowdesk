# Synthetic-OI on correct 0DTE data — three lenses + roadmap (harness v1)

> **STATUS: Re-run on CORRECT 0DTE data (Jun 5/8/9/10 2026), zero-API, from disk.**
> This supersedes the withdrawn quarterly-contaminated results. The greek layers
> now price sanely (the 140–290% IV artefact is gone). Findings here are
> **structural** on 4 trading days — NOT price-validated. Predictive ranking of the
> lenses requires the ~90-day forward test (done manually by the operator).
> Placed in `docs/research/empirical/`, NOT `verified/`.

Scripts: [`/analysis/rerun_zerodte.py`](../../../analysis/rerun_zerodte.py) (greek
re-run via the validated `build_snapshot` + `surface.fit_svi`),
[`/analysis/synthetic_oi_v3.py`](../../../analysis/synthetic_oi_v3.py) (VOL vs OI vs
FLOW head-to-head). Data: `data/raw/zerodte/` (correct daily 0DTE families
E2A–E2D/EW1 for ES, Q2A–Q2D/QN1 for NQ; underlying ESM6/NQM6).

---

## 1. Vol surface — theory-consistent ✅ (the clean win)

Re-running `surface.fit_svi` on correct 0DTE data, at the 12:30 ET sample:

| Day | regime | ATM vol | skew | RMSE |
|---|---|---|---|---|
| Jun 5 ES | calm | **22.1%** | −1.27 | 0.0027 |
| Jun 8 ES | calm | **23.0%** | −2.56 | 0.0063 |
| Jun 9 ES | crash | **43.3%** | −0.89 | 0.0215 |
| Jun 10 ES | crash | **37.0%** | −4.97 | 0.0081 |
| Jun 10 NQ | crash | **54.3%** | −8.70 | 0.0083 |

- ATM vol **22–54%** (was 140–560% on wrong-tenor data) — the artefact is gone.
- Vol **rises on crash days** (calm ~22% → crash 37–54%), exactly as expected.
- **Put skew negative every day** (downside-fear, the correct equity shape).
- RMSE 0.003–0.02, all arb-free. The surface layer is sound on correct data.

## 2. Three positioning lenses — VOL vs OI vs FLOW

For each near-money strike, dealer-GEX `= Σ sign · γ · Q · M · F² · 0.01`, varying
what `(sign, Q)` is:

| Lens | sign | Q | What it is |
|---|---|---|---|
| **VOL** | static +1c/−1p | cumulative volume | our locked engine (decision #1) |
| **OI** | static +1c/−1p | open interest | classic SpotGamma `Γ·OI` formula |
| **FLOW** | **−net aggressor** | \|net signed flow\| | our edge: dealer sign from REAL CME aggressor side |

**Honest findings on 4 days (sign-agreement across ~25 valid minutes):**

- **VOL ≈ OI in regime sign (~92%).** Swapping volume→OI (the genuine SpotGamma
  formula) mostly rescales (OI magnitudes 10–100× larger), it rarely flips the
  regime sign. So "OI-GEX is completely different from VOL" would be an
  **over-claim** at the headline-signal level — they largely agree on direction.
- **FLOW differs from VOL ~36% of minutes**, concentrated on the **crash days**
  (Jun 9/10): VOL/OI read −1 (short gamma / volatile), FLOW reads +1.
- **OI coverage = 62%** of legs had an OI record in the scoped statistics pull —
  OI-GEX here is built on partial data. Documented, not hidden.

## 3. The crash-day divergence — bug or the whole point?

On Jun 9 (price 7457→7290, a real crash), FLOW says +1 while VOL/OI say −1. First
read: "FLOW looks wrong on the most important day." Better read:

> FLOW measures **flow** (what's trading now); VOL/OI measure **stock** (accumulated
> positioning). A flow indicator is *designed to lead* a stock indicator — so at a
> regime turn (a crash) FLOW SHOULD diverge from VOL/OI. The real question is not
> "which is right today" but "which one **moves first**" — and that is precisely
> what a forward test answers.

So the divergence is **expected behaviour of a flow vs stock signal**, not proof of
error. Whether FLOW *leads* price (contrarian/early) or is just noise is **not
decidable on 4 correlated days** — it is the core question for the 90-day forward test.

## 4. Synthetic OI is a FAMILY, not one formula — roadmap

The three lenses above are 3 points on a spectrum. More robust formulations the
data supports (rough → robust):

1. VOL-GEX (have) · 2. OI-GEX (have) · 3. FLOW-GEX (have)
4. **Hybrid OI-anchored + flow-update (recommended next):**
   `dealer_pos(K,t) = −[ OI_open·sign_prior + Σ_{trade≤t} signed_size·w(open/close) ]`
   — anchors to carried-in stock (what FLOW ignores) AND updates it with real-time
   aggressor flow (what OI ignores). This is the vendors' "options inventory model"
   in spirit; most robust because crash-day no longer rides on raw flow alone.
5. Decay-weighted flow (recent flow > old; mitigates round-trip double-count).
6. Size-tiered classification (large=institutional/dealer, small=retail proxy).
7. **Total-hedging map (gamma + charm + vanna):** for 0DTE, charm explodes into
   16:00 ET — a gamma-only map understates afternoon dealer pressure. vanna/charm
   are already FD-validated in the engine.
8. State-space / Kalman latent-inventory (heavy; future).

**Irreducible proprietary gap (true for every vendor incl. SpotGamma):** the
*direction* of carried-in OI is unknowable from the tape, so all OI-based lenses
fall back to the static long-call/short-put convention for the opening stock. Our
native CME aggressor side lets FLOW (and the hybrid #4) do the *intraday* direction
better than Lee-Ready-based vendors — that is the genuine, defensible edge.

## 4b. Formula #4 BUILT — hybrid OI-anchored + flow-update ✅

Implemented in [`/analysis/synthetic_oi_v4.py`](../../../analysis/synthetic_oi_v4.py)
after a 2-agent deep-research pass (methodology + data-feasibility). Per strike `K`,
type `τ`, minute `t`, dealer **signed contract position**:

```
Q4(K,τ,t) = s_static(τ)·OI_open(K,τ)  +  Σ_{trade i≤t}(−a_i)·size_i·w
GEX4(t)   = Σ_K Σ_τ Γ_τ · Q4 · M · F² · 0.01      (locked kernel, signed-Q)
```
- `s_static` = +1 call / −1 put (irreducible fallback for carried-OI direction).
- `OI_open` = prior-session settled OI (`ts_ref` = prior session — genuine
  carried-in stock, static intraday; null sentinel 2147483647 dropped).
- `a_i` = native CME aggressor (B/A/N); dealer takes the opposite (`−a_i`).
- `w` ∈ [0,1] = open/close weight (the one proprietary knob), **tunable**, swept
  {0, 0.5, 1}. `w=0` ⇒ pure OI-GEX; `OI_open=0, w=1` ⇒ pure FLOW-GEX. #4 strictly
  generalizes every prior lens. **Non-circular** (never touches same-day ΔOI).

**Data-feasibility (measured, 4 days):** aggressor `N=0%` (zero directional info
lost — the edge over Lee-Ready is maximal); OI is true carried-in stock, static
intraday; ES near-money OI coverage 97–100% and flow/OI 0.2–0.6 (anchor dominates,
flow refines) → **ES robust**. NQ OI coverage 66–87%, flow/OI 0.67–1.25 (flow swamps
a thin, partly-missing anchor) → **NQ flagged FRAGILE**. vol/OI 2–13× everywhere ⇒
heavy round-tripping, so the open/close (`w`) attribution is unobservable and does
real work — an explicit model assumption, not data.

**Result (structural, 4 days):**
- ES: `w=0`→`w=1` flips regime sign in only ~9% of minutes — the **OI anchor
  dominates; flow is a measured refinement, not a hijack.**
- **#4 fixes the v3 crash-day problem:** FLOW-only read +1 during the Jun 9/10
  crash (looked wrong); #4 reads **−1 (volatile) on every crash day** because the OI
  anchor keeps the regime sane while flow only tunes magnitude. The hybrid resolves
  the stock-vs-flow tension — stock gives the correct base, flow adds real-time
  sensitivity, without raw flow hijacking the signal. This is *why* #4 is more robust.
- NQ flips more (thin anchor) — consistent with the fragility flag, not trusted.

**Honest bound:** #4 is a product-grade positioning lens for **ES**; it is NOT
proven predictive on 4 correlated days. Whether `w>0` (flow) adds forecasting power
over `w=0` (pure OI) is the central question of the operator's ~90-day forward test.



- **Is:** correct 0DTE data exists and prices sanely; three methodologically-sound
  positioning lenses run on it; FLOW is genuinely different from VOL (not "VOL with
  a fancy name"); a clear roadmap to a more robust hybrid (#4) and total-hedging (#7).
- **Isn't:** any claim that one lens predicts price better. VOL≈OI on sign; FLOW
  diverges but its crash-day behaviour is unproven (leads? noise?). Ranking the
  lenses is the **~90-day manual forward test** (operator), per the one-month plan.

See: [`symbology-0dte-findings.md`](symbology-0dte-findings.md) (how the correct
data was obtained), [`lapis1-doi-reconciliation.md`](lapis1-doi-reconciliation.md)
(the T-independent flow-vs-ΔOI baseline, still valid).
