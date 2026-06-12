# Data Symbology Bug + 0DTE Findings — Critical Record (harness v1)

> **STATUS: Critical methodology finding from research (RISET1407.md, 2026-06-13).**
> The 8-day case-study dataset was pulled with the WRONG symbology — it contains
> QUARTERLY options, not 0DTE. The engine is correct; the data acquisition was
> wrong. This document records the root cause, the fix recipe, and which prior
> findings are contaminated. Placed in `docs/research/empirical/`, NOT `verified/`.

Source of truth for the claims below: [`../RISET1407.md`](../RISET1407.md)
(deep research answering the symbology/0DTE/OPRA questions, primary-source cited).

---

## 1. The bug (definitive root cause)

**FlowDesk is a 0DTE terminal. The engine prices everything as 0DTE** (`t_expiry_from_clock`
= time to 16:00 ET *today*, locked decision #3). That is correct by design.

**But the 8-day data I pulled has NO 0DTE contracts.** I used Databento parent
symbology `ES.OPT` / `NQ.OPT`. Per Databento docs (RISET1407 §3D, [FAKTA]):

> "`ES.OPT` refers to all **quarterly** E-mini S&P 500 options and option spreads."

So `ES.OPT`/`NQ.OPT` **exclude every daily/weekly family.** The pull returned only
quarterlies (ESM6 = Jun-18, ESZ6 = Dec-18, …). The nearest expiry on Jun 2 was
**16 days out**, on Jun 9 was **9 days out** — never same-day.

**Consequence:** the engine priced 9–16-day contracts as T ≈ 0.14 days → the IV
solver forced implied vol to **140–290%** to fit. That is a pure **artefact**, not
signal.

## 2. 0DTE /ES & /NQ DO exist — this is fixable (not a product death)

[FAKTA, CME sources in RISET1407 §3A] Both ES and NQ have **daily expiries Mon–Fri**
(Tuesday & Thursday added 2022), European-style. The daily/weekly families have
**different product roots**:

| Instrument | Daily/weekly roots |
|---|---|
| ES | E1A–E5A (Mon), E1B–E5B (Tue), E1C–E5C (Wed), E1D–E5D (Thu), EW1–EW4 (Fri), EW (EOM) |
| NQ | Q1A–Q5A, Q1B–Q5B, Q1C–Q5C, Q1D–Q5D (Mon–Thu), QN1–QN4 (Fri) |
| (quarterly) | ES / NQ — the AM-settled 3rd-Friday contracts I wrongly pulled |

## 3. The fix — deterministic, anti-guess re-pull recipe

RISET1407 honestly flags the exact Databento parent strings for weekly families as
`[PERLU VERIFIKASI runtime]` — so **do NOT hard-code `E1A.OPT` etc.** The robust
method (RISET1407 §3D) is expiry-filtering on the definition schema:

```python
# Pull ALL option definitions for the session day, then filter to same-day expiry.
defs = client.timeseries.get_range(
    dataset="GLBX.MDP3", schema="definition", stype_in="parent",
    symbols=["ES.OPT", "NQ.OPT"],   # NOTE: returns quarterly only — see caveat
    start=SESSION, end=SESSION_PLUS_1,
)
df = defs.to_df()
zero_dte = df[df["expiration"].dt.date == SESSION_DATE]   # <-- the 0DTE filter
zero_dte = zero_dte[zero_dte["instrument_class"].isin(["C", "P"])]
# use zero_dte["raw_symbol"] / instrument_id for the trades/statistics/bbo pulls
```

**OPEN VERIFICATION (when Databento unlocks):** confirm whether `ES.OPT` parent +
expiry-filter actually surfaces the daily families, or whether the daily roots must
be enumerated as separate parents (`E1A.OPT`, …). Verify the real `asset` value from
the definition output **before** hard-coding anything. This is the one runtime
check that closes the bug for good.

## 4. GLBX vs OPRA — stay on GLBX (decided, evidence-based)

RISET1407 §3B/§3C, with primary sources:

- The famous "0DTE" phenomenon is **SPX (OPRA)** — ~2.3M contracts/day, ~59% of SPX
  volume (Cboe 2025). [FAKTA]
- But **OPRA has no aggressor side** (`side` always `N` → forces Lee-Ready,
  72–93% accurate, worst exactly in the fast 0DTE afternoon) **and does not carry
  options-on-futures at all** (no /ES /NQ). [FAKTA, Databento]
- **GLBX/ES-NQ wins on what FlowDesk needs:** native aggressor side (no Lee-Ready)
  + Black-76, matching the existing locked architecture.

**Decision: fix GLBX symbology, do not migrate to OPRA.** (Migrating would discard
the native-aggressor advantage that makes the HIRO/flow layer sound.)

## 5. Contamination map — which prior findings survive

Because the engine priced quarterlies at the wrong T, **every greek-dependent
result on the 8-day data is suspect.** Honest status of prior commits:

| Prior finding (commit) | Uses greeks? | Status now |
|---|---|---|
| **Lapis 1** ΔOI recon (50.8%, `1b03ffd`) | No — pure flow vs ΔOI | ✅ **valid** (T-independent) |
| **DDOI** head-to-head (artefact, `95e7f64`) | No — pure flow vs ΔOI | ✅ **valid** |
| **Synthetic-OI** direction diagnostic | Partial — direction is flow-based | ⚠️ direction valid; gamma-weighted magnitude suspect |
| Case study regime/flip/walls (`95e7f64`) | Yes (GEX = γ·VOL) | ❌ **contaminated by wrong T** |
| VEX/CHEX (`95e7f64`) | Yes (vanna/charm) | ❌ **contaminated** |
| SVI surface, ATM vol 140–290% (`95e7f64`) | Yes (IV) | ❌ **artefact** — the 140–290% IS the tell |

The "theory-consistent wins" (VEX/CHEX, surface) I reported earlier must be
**downgraded**: they were computed on mispriced greeks. Lapis 1 and DDOI stand
because they never touch greeks.

## 6. Synthetic OI or VOL? — the answer

- **Product GEX: VOL** — locked contract (decision #1), unchanged. No empirical
  basis exists to replace it; synthetic-OI was never validated against price.
- **Synthetic-OI: a real, methodologically-correct engine** (4-way reconstruction,
  M=0 assumption labeled, direction non-circular) — but its accuracy is **unknown**:
  magnitude uses ΔOI (circular vs a ΔOI test) and there is no price test. Real
  validation needs Lapis 2 (~90 days) on **correctly-pulled 0DTE data**.
- DDOI (the time-weighted proxy) is **dead** — diagnostics proved its edge was a
  thin-key + base-rate artefact (n≥10 collapses to 50.0%, 200-perm null p=0.205).

## 7. What must happen before ANY 8-day number is trusted again

1. **Databento unlock** (account locked — human action: support@databento.com,
   rotate API key after).
2. **Re-pull with the §3 recipe** — verify daily 0DTE families actually land.
3. Re-run the greek-dependent layers (case study, VEX/CHEX, surface) on real 0DTE.
4. Only then is Lapis 2 (predictive validation) meaningful.

Until then: **only the flow-based, T-independent findings (Lapis 1, DDOI verdict)
are safe to cite.**

See also: [`lapis1-doi-reconciliation.md`](lapis1-doi-reconciliation.md),
[`track-f-ddoi-exposure-vol.md`](track-f-ddoi-exposure-vol.md),
[`case-study-gex-jun2026.md`](case-study-gex-jun2026.md).
