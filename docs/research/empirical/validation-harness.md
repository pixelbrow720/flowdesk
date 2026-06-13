# Validation Harness — Mechanism Built, Evidence Pending (v1)

> **STATUS: Mechanism, NOT evidence.** This documents an offline validation
> harness that *computes* the right descriptors end-to-end on the 4 correct 0DTE
> sessions. It is **not** in [`../verified/`](../verified/): nothing here is a
> validated signal. The real test is the operator's ~90-day forward run, which
> calls this same code. A look-ahead bug and a distance-baseline bias were caught
> and fixed in adversarial review (see §5) — treat all numbers as provisional.

**Date:** 2026-06-13 · **Instruments:** /ES, /NQ · **Sessions:** Jun 5/8/9/10
2026 (4 days, one a crash arc) · **Data:** Databento GLBX.MDP3 (definition, bbo-1m,
trades, statistics), all gitignored. Harness:
[`/analysis/harness/metrics.py`](../../../analysis/harness/metrics.py) (pure core,
17 unit tests) + [`/analysis/harness/run_validation.py`](../../../analysis/harness/run_validation.py)
(dbn-streaming driver).

---

## 1. What this addresses

`docs/08-status-and-gaps.md` #1: the engine computes GEX/DEX/levels nobody has
tested against reality. This harness builds the **machine** to test two questions
over a 90-day window:

1. **Reconciliation** — does the synthetic dealer positioning (VOL + native
   aggressor flow) line up with **settled open interest**?
2. **Price interaction** — does price get **attracted to / pinned at** the
   gamma-flip and largest-GEX levels more than at comparable random strikes?

The metric MATH lives in the pure, unit-tested `metrics.py`; the driver only does
dbn streaming + `build_snapshot` calls + printing. So the part that must be
*correct* is tested without market data; the part that needs *data* is a thin shell.

## 2. The two hard constraints this data imposes (honest scope)

- **Directional ΔOI reconciliation is structurally impossible on 0DTE.** The
  Lapis-1 method matched contracts across consecutive days and used the *sign* of
  `ΔOI = OI(T) − OI(T−1)`. 0DTE contracts are listed and expire the **same**
  session: zero cross-day key overlap (verified: symbol overlap 0/0/0/0), and they
  start at OI=0 so `ΔOI_session ≡ OI_settle ≥ 0` is **sign-definite**. A
  sign-agreement test carries zero information here. Only the **magnitude**
  relation is testable.
- **Magnitude reconciliation is confounded by volume.** A heavily-traded leg has
  both large |flow| and large settled OI simply because it is active. So the
  headline is the **partial** Spearman of |flow| vs OI *holding cumulative volume
  fixed* — the activity-independent part. The raw rho is reported too, labelled as
  the confounded one.

## 3. What the harness computes

| Metric | Definition | Honesty guard |
|---|---|---|
| `magnitude_reconciliation` | Spearman \|net aggressor flow\| vs settle-OI per leg; raw **and** volume-partialled | partial control; no verdict string |
| `level_attraction_vs_baseline` | normalized open→close distance shrink to a level, vs **distance-matched** baseline strikes | level taken from the **open** snapshot (causal); baseline matched on \|strike−forward\| |
| `pin_rate` | fraction of per-minute closes within one strike step of the level | reported with n; descriptive only |

Walls are **not** scored: they need OI, and the only OI available is the EOD
settle — using it at the open would be look-ahead. Walls belong to a separate
OI-aware pass.

## 4. First results (4 days — descriptive, NOT a signal)

- **Reconciliation:** raw rho ≈ **+0.17 … +0.46** across session-instruments, but
  the volume-controlled `rho|vol` **collapses to ≈ +0.08 … +0.24** (one negative).
  First honest read: the apparent flow↔OI reconciliation is **mostly raw activity**
  ("active strikes are active"), not positioning skill. Consistent with Lapis-1's
  "magnitude real, direction not" finding.
- **Price interaction:** excess-attraction is small and mixed in sign; pin-rate ≈ 0
  at one-step tolerance. **No pinning signal visible** — as expected at n=4 days;
  not evidence either way.
- Thin/illiquid session-instruments are **excluded with logging** (a 6-minute floor;
  Jun 9 /NQ dropped at 5 valid minutes), not silently passed.

## 5. Bugs caught in adversarial review (why this is provisional)

The red-team stage caught two artefacts that *faked* signal in the first cut:

1. **Look-ahead in the attraction test.** Levels were taken from the **close**
   snapshot, where gamma-flip/largest-GEX sit near the current price by
   construction — so "price reached them by close" was tautological (excess +7…+13).
   Fixed to take levels from the **open** snapshot and measure forward migration.
2. **Unfair baseline.** Attraction was compared to the mean over **all** axis
   strikes (mostly far from spot), biasing a near-the-money level's number upward.
   Fixed to a **distance-matched** baseline (`distance_matched_levels`).

Both fixes shrank the headline numbers toward zero — i.e. the original "signal" was
the artefact. The volume-partial control (§2) likewise dissolved most of the
reconciliation rho.

## 6. What remains (the gap is still open)

This is the **mechanism**, not the verdict. To turn it into evidence:
- Run the operator's **~90-day** forward pull through the same `run_validation.py`
  (manual; respects the anti-lock Databento protocol — batch, 1 req/schema, no
  aggressive retry, `get_cost` first).
- Add an **OI-aware wall pass** (needs intraday OI, not just settle).
- Only then promote any finding toward [`../verified/`](../verified/).
