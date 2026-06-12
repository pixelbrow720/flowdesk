# Exploratory GEX Case Study — Jun 1–10 2026 (DESCRIPTIVE)

> ⚠️ **CONTAMINATION NOTICE (2026-06-13): this case study ran on WRONG-TENOR data.**
> The 8-day dataset is QUARTERLY options pulled via `ES.OPT`/`NQ.OPT`, not 0DTE
> (see [`symbology-0dte-findings.md`](symbology-0dte-findings.md)). The engine
> priced 9–16-day contracts as 0DTE (T≈0.14 days), so all GEX values — regime sign,
> gamma-flip, walls — rest on mispriced gamma. **Treat every number here as
> provisional and WITHDRAWN pending a correct 0DTE re-pull.** The narrative shape
> (calm vs crash days) loosely tracks price, but the GEX magnitudes are not trustworthy.

> **STATUS: Exploratory, descriptive, hypothesis-generating. This is NOT Lapis 2.**
> No walk-forward, no FDR verdict, no significance test, no "validated" claim.
> A single 8-day correlated episode builds intuition and catches gross bugs — it
> does **not** confirm any hypothesis. Placed in
> [`../empirical/`](.), not [`../verified/`](../verified/).

**Window:** Jun 1–10 2026 (8 trading days, one crash→correction→stabilization arc)
· **Instruments:** /ES, /NQ · **Engine path:** real `build_snapshot` (Black-76 →
IV → exposure → levels), 390 RTH minutes/session, true same-day 0DTE expiry where
present. Harness: [`/analysis/case_study.py`](../../../analysis/case_study.py).
Charts: `/analysis/charts/<instr>_<day>.png` (price vs gamma-flip + walls; not
committed — regenerable).

---

## 1. Per-day summary (descriptive)

Regime sign = sign of net GEX at mid-session (open/close show 0 as the 0DTE chain
is pre-open / expired). Walls read from a representative mid-session frame.

### /ES
| Day | regime (mid) | range% | flip o→c | note |
|---|---|---|---|---|
| Jun 1 | +1 pinning | 0.7 | 7585→7610 | calm |
| Jun 2 | +1 | 0.4 | 7600→7625 | calm |
| Jun 3 | +1 | 0.7 | 7610→7575 | calm |
| Jun 4 | +1 | 0.9 | 7550→7605 | calm |
| Jun 5 | **−1 volatile** | 2.2 | 7550→7405 | selloff begins |
| Jun 8 | −1 | 1.0 | 7455→7415 | |
| Jun 9 | −1 | **3.2** | 7460→7390 | crash (low 7252) |
| Jun 10 | −1 | 1.7 | 7355→7290 | continued decline |

### /NQ
| Day | regime (mid) | range% | flip o→c | note |
|---|---|---|---|---|
| Jun 1 | +1 | 1.3 | 30350→30550 | calm |
| Jun 2 | +1 | 0.9 | 30550→30700 | calm |
| Jun 3 | −1 | 0.9 | 30750→30650 | |
| Jun 4 | +1 | 1.5 | 30275→30500 | |
| Jun 5 | −1 | 3.7 | 30025→29050 | selloff |
| Jun 8 | +1 | 1.3 | 29525→29450 | |
| Jun 9 | −1 | **5.3** | 29750→29100 | crash (low 28257) |
| Jun 10 | +1 | 2.6 | 28850→28625 | |

## 2. What is consistent with theory (descriptive only)

- **Net-GEX sign separates regimes cleanly for /ES:** the four calm days (Jun 1–4)
  are gamma-positive with sub-1% ranges; the selloff/crash days (Jun 5, 8, 9, 10)
  are gamma-negative with 1.0–3.2% ranges. The flip to negative coincides with the
  selloff onset (Jun 5) and persists through the correction.
- **Gamma-flip tracks price down during the crash** (e.g. /ES flip 7550→7405 on
  Jun 5, 7460→7390 on Jun 9).
- /NQ is noisier (Jun 3, 8, 10 alternate sign) — consistent with the caveat that
  one instrument's per-day regime is not a robust signal at n=8.

This is **descriptively** in line with the intuition behind H1 (pinning) and H3
(regime-vol), but with n=8 correlated days it can only be an **observation**, never
a test.

## 3. H2 (wall reaction) — INDICATIVE ONLY

Aggregated across all 16 sessions: **258 wall touches, 160 "rejections" (62%)**,
where a touch = price within 0.15% of a call/put wall and a rejection = price moves
away over the next 3 minutes.

**This is not evidence.** Caveats: (a) intraday events within one 8-day correlated
episode are not independent; (b) no random-level baseline was tested, so 62% has
nothing to be compared against; (c) "touch" and "rejection" are operational
definitions, not the locked ones (G.10.2 is still open). It is a sanity signal that
walls are placed where price interacts with them, nothing more.

## 4. NOT claimed

- H1 (pinning) and H3 (regime-vol) are **not tested** — per-day units, 8 days are
  far below the power needed; shown only as descriptive observations.
- No statistical vs economic significance split (tick costs) — that is Lapis 2.
- The real confirmatory verdict (predictive H1–H3, walk-forward 60/30, FDR, block
  bootstrap, random baseline) **remains deferred** to a ~90-day multi-regime dataset
  with a locked OOS split. This case study is intuition and sanity, not a substitute.

See the confirmatory Lapis 1 result:
[`lapis1-doi-reconciliation.md`](lapis1-doi-reconciliation.md).
