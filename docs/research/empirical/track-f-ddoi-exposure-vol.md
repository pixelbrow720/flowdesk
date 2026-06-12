# Track F + DDOI — Exposure & Vol-Surface Layers (harness v1, exploratory)

> ⚠️ **CONTAMINATION NOTICE (2026-06-13): the greek-based results below were
> computed on WRONG-TENOR data.** The 8-day dataset was pulled with `ES.OPT`/`NQ.OPT`
> parent symbology, which returns QUARTERLY options, not 0DTE (see
> [`symbology-0dte-findings.md`](symbology-0dte-findings.md)). The engine priced
> 9–16-day contracts as T≈0.14 days, so the IV / vanna / charm here are artefacts —
> the **140–290% ATM vol is the tell**, not a real crash signal. VEX/CHEX and the
> SVI surface findings are therefore **WITHDRAWN pending a correct 0DTE re-pull.**
> The DDOI section (flow-vs-ΔOI, no greeks) is unaffected and still valid.
>
> ✅ **UPDATE 2026-06-13: correct 0DTE data NOW EXISTS** for Jun 5/8/9/10 (`data/raw/zerodte/`,
> IV verified sane ~26.7%, proper put skew). VEX/CHEX and SVI remain WITHDRAWN until
> RE-RUN on that data (re-run still pending; only 4 of the 8 days were re-pulled).

> **STATUS: Exploratory analysis layer, 8-day sample. NOT validated, NOT in the
> Snapshot.** Built on the VALIDATED engine core (`black76.vanna/charm` FD-checked,
> `surface.fit_svi`, `engine.iv`) but run on a single 8-day correlated episode
> (Jun 1–10 2026). Lives in `analysis/`; integrating any of this into the Snapshot
> is `schema_version+1` — a human decision, deliberately not taken here. Placed in
> `docs/research/empirical/`, NOT `verified/`.

**Scripts:** [`/analysis/vex_chex.py`](../../../analysis/vex_chex.py),
[`/analysis/surface_fit.py`](../../../analysis/surface_fit.py),
[`/analysis/ddoi.py`](../../../analysis/ddoi.py). Data: case-study CSVs (ES/NQ,
8 trading days). Dealer signs + VOL basis identical to the locked `exposure.py`.

---

## 1. VEX / CHEX exposure (TRACK F.4) — theory-consistent ✅

`VEX = Σ dealer_sign · vanna · VOL · M`, `CHEX = Σ dealer_sign · charm · VOL · M`,
using the FD-validated `black76.vanna/charm` and the locked dealer convention.

**Finding (descriptive):** |CHEX| **grows sharply from open to late session** on
/ES — ratio (late/open) ≈ **80–470×** across all 8 days. This is exactly the F.4
prediction: charm magnitude builds as 0DTE expiry approaches (16:00 ET), the
mechanism behind end-of-day "pin" pressure. VEX collapses toward ~0 at the close
(vanna → 0 as T → 0), also as expected.

| /ES day | CHEX(open) | CHEX(late) | late/open |
|---|---|---|---|
| Jun 1 | -1.69e6 | -4.06e8 | 240× |
| Jun 5 (selloff) | -1.73e6 | -6.85e8 | 397× |
| Jun 9 (crash) | -7.80e6 | -6.33e8 | 81× |
| Jun 10 | -1.12e6 | -5.31e8 | 473× |

(/NQ same direction, noisier — fewer near-money strikes; Jun 5/10 late=0 where the
late sample had no priced near-money chain.)

**Caveat:** descriptive over 8 correlated days; not a test that CHEX *predicts*
the close. But the sign and the open→close build are mechanically correct — the
VEX/CHEX engine works and produces meaningful exposure.

## 2. SVI vol surface + expected move (TRACK F.2/F.3) — theory-consistent ✅

Raw-SVI slice fit (`surface.fit_svi`, validated) over the per-minute 0DTE smile.

**Findings (descriptive):**
- **Put skew** (negative `d(IV)/dk` at ATM) on ~15/16 day-instruments — the typical
  equity downside-fear shape.
- **ATM vol spikes on the crash days:** /ES peaks Jun 9 at **1.81** (vs ~1.20–1.55
  calm), /NQ peaks Jun 9 at **2.89** (vs ~2.0–2.4). Expected move widens in step
  (/ES EM 253 pts on Jun 9 vs ~176–223 calm).
- Most slices **arbitrage-free** (Gatheral conditions).

**Honest caveats (flagged, not hidden):** the Jun-9 crash smile is the hardest to
fit — /ES Jun-9 RMSE 0.29 (vs ~0.04 normal), and /NQ Jun-9 shows an anomalous
**positive** skew (+11.3) with RMSE 0.57. On the single most violent day the smile
is genuinely irregular; the fit degrades there. That is an artefact of the episode,
not a code bug, but it means crash-day surface params should not be over-read.

## 3. DDOI head-to-head vs VOL (TRACK D.6) — honest negative ⚪

DDOI reconstructs a signed dealer-inventory change by classifying each trade
OPEN vs CLOSE (momentum=open, reversal=close; **never peeks at ΔOI** — non-circular),
then scores against ΔOI on the *same* G.4.4 metric core as Lapis 1.

```
  mean sign-agreement:  VOL=50.8%   DDOI=49.2%   (baseline random=50%)
  => NO MEANINGFUL DIFFERENCE (Δ=-1.6 pts on 8-day sample)
```

**Honest read — this did NOT beat the baseline, and I'm reporting it straight.**
But the numbers reveal *why*, which is itself useful: the Spearman rho is
**identical** between VOL and DDOI on every pair (0.273, 0.224, 0.306, …). That
means the open/close classifier rarely fired a "close" — most per-strike intraday
flow is one-directional, so `|ddoi_position| ≈ |vol_sum|` in rank, leaving sign
essentially unchanged. A real DDOI improvement needs (a) finer open/close
information than the tape labels (true position tracking), and/or (b) the ~90-day
multi-regime sample to expose round-trip days where the classifier matters.

**The win here is the machine, not the number:** a non-circular DDOI reconstruction
now runs and is measurable head-to-head against VOL on identical metrics — exactly
the "parallel, measurable layer" the verified report (D.6) calls for. On 8 days it
reads flat; that is a true finding, not a failure to hide.

## 4. What this is / isn't

- **Is:** three working analysis layers on validated engine math, producing
  theory-consistent exposure (VEX/CHEX), a sane vol surface (SVI/skew/EM), and a
  measurable DDOI reconstruction — all over real /ES /NQ data.
- **Isn't:** validated signals. 8 correlated days, no walk-forward, no FDR, no OOS.
  Nothing here is in the Snapshot (would be `schema_version+1`).
- **Next (gated on ~90-day data + your call):** re-run all three at scale; for DDOI,
  add round-trip-aware classification; decide Snapshot integration as a contract bump.

See also: [`lapis1-doi-reconciliation.md`](lapis1-doi-reconciliation.md),
[`case-study-gex-jun2026.md`](case-study-gex-jun2026.md).
