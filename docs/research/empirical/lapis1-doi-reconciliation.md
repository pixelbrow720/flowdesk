# Lapis 1 — ΔOI Reconciliation: Empirical Finding (harness v1)

> **STATUS: Empirical finding, harness v1. Positive-control PASSED; awaiting
> full-dataset confirmation (Lapis 2, ~90 days).** This document is deliberately
> NOT in [`../verified/`](../verified/): that folder is the locked, independently
> re-derived source of truth. The harness here is newly built (and was buggy
> mid-development — see §5), validated only by a synthetic positive control and a
> single 8-day correlated episode. It has not cleared the `verified/` bar.

**Date:** 2026-06-12 · **Instruments:** /ES, /NQ · **Window:** Jun 1–10 2026 (8
trading days) · **Data:** Databento GLBX.MDP3 (definition, statistics, trades).
Harness: [`/analysis/lapis1.py`](../../../analysis/lapis1.py) +
[`/analysis/lapis1_control.py`](../../../analysis/lapis1_control.py).

---

## 1. What was tested (Track G.4)

Does the **direction** of net option aggressor flow (a proxy for dealer
positioning under the VOL + static-dealer-sign methodology) agree with the
official daily change in open interest, `ΔOI = OI(T) − OI(T−1)`, matched per
`(root, type, strike, expiry)` across consecutive days?

- **Flow** = `Σ aggressor_sign · size` per key (B=+1, A=−1, N=0), from `trades.side`.
- **ΔOI** = final-settlement OI difference (dedup: latest `ts_recv` per key/day).
- **Metrics (G.4.3):** sign-agreement rate (random baseline 50%), Spearman rank
  IC of `|flow|` vs `|ΔOI|`, weighted directional error (wDE).
- **Verdict gate (G.4.4):** PASS if sign ≥ 60% **and** Spearman ≥ 0.2 (p<0.05);
  MARGINAL 55–60%; FAIL < 55%.

## 2. Result — FAIL on directional reconciliation

```
       pair  n_keys  sign%  spearman         p     wDE  verdict
  06-01→02    420    45.7     0.273  1.24e-08   0.406  FAIL
  06-02→03    394    53.6     0.224  7.05e-06   0.477  FAIL
  06-03→04    427    49.9     0.306  1.01e-10   0.571  FAIL
  06-04→05    517    50.1     0.335  4.94e-15   0.479  FAIL
  06-05→08    588    47.8     0.373  7.76e-21   0.460  FAIL
  06-08→09    577    55.5     0.362  2.43e-19   0.455  MARGINAL
  06-09→10    619    53.0     0.391  4.60e-24   0.418  FAIL
  mean sign-agreement: 50.8%
```

## 3. Interpretation (what it does and does NOT mean)

- **Sign-agreement 50.8% ≈ random (50%).** The *direction* of aggressor flow does
  not recover the *direction* of ΔOI better than chance. 6/7 pairs FAIL, 1 MARGINAL.
- **Spearman 0.22–0.39, all p ≪ 0.05.** The *magnitude* relationship is real and
  highly significant — strikes with large aggressor flow also have large |ΔOI| —
  but that is **co-activity / liquidity**, not directional positioning.
- **Mechanism (open/close ambiguity):** a buy-aggressor trade can OPEN or CLOSE a
  position, so signed aggressor flow cannot recover signed ΔOI. This is exactly
  the "inti gap metodologi" the verified report flags (D.6) and that **DDOI (v3)**
  is designed to close.
- **This does NOT trigger removal of VOL-GEX.** Decision #1 (VOL basis) is locked.
  The harness now *measures* a structural bias that was previously only assumed,
  giving an empirical baseline (50.8%) that a future DDOI layer must beat.
- **Scope:** Lapis 1 matches across ALL expiries (dealers hedge the whole book),
  so this is not a 0DTE-specific statement. It is not a price-prediction test
  (that is Lapis 2 / H1–H3, deferred).

## 4. Positive control — why the FAIL is trusted (not a dead metric)

A FAIL is only meaningful if the metric *can* detect signal. The shipped metric
core (`pair_metrics`) was run on synthetic data with a known injected signal:

```
   tier     n   sign%  spearman          p  verdict  expect
PERFECT    400  100.0     1.000          0     PASS    PASS  OK
 STRONG    400   82.2     0.961  1.95e-224     PASS    PASS  OK
   NULL    400   47.0     0.094     0.0602     FAIL    FAIL  OK
```

The metric scores PASS on real/strong signal and FAIL on noise. **The real-data
50.8% sits in the NULL bracket**, so the FAIL is a genuine finding about the
VOL + static-sign methodology — not a broken or dead metric.

## 5. Harness caveats (why this is v1, not verified)

- **Single correlated episode** (8 days, one crash→correction arc). No multi-regime
  generalization.
- **Bugs found & fixed during development** (honesty ledger): per-day vs cumulative
  instrument resolution; Jun-9 OI dedup (latest `ts_recv`; old/new file overlap);
  bbo-1m price extraction (`levels[0].bid_px`, not flat `bid_px_00`). These were
  caught via verification, but a v1 harness with a fresh bug history has not earned
  `verified/` status.
- **Open/close split not modeled** — the core limitation; resolving it *is* DDOI.
- **Lapis 2 (predictive H1–H3 + walk-forward 60/30 + FDR + block bootstrap)
  remains deferred** until ~90 days of multi-regime data with a locked OOS split.

## 6. Reproduce

```bash
# from repo root, with data/case_study/raw/{definition,statistics,trades} present
.venv/Scripts/python.exe analysis/lapis1_control.py   # positive control (synthetic)
.venv/Scripts/python.exe analysis/lapis1.py           # real-data reconciliation
```

See also the exploratory GEX case study (descriptive, NOT Lapis 2):
[`case-study-gex-jun2026.md`](case-study-gex-jun2026.md).
