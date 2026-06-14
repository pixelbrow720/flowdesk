# 08 — Status & Gaps (the honest map)

This is the document to read when the project "feels done but lacking." It is the
backlog. The backend is **code-complete and well-engineered**, but it is built on
the **methodologically weakest version of the core signal** and is
**validation-incomplete**. Both things are true at once.

## What is genuinely solid ✅

- **Deterministic, pure engine** with a golden fixture. Same inputs → same Snapshot.
- **Cross-language contract** byte-for-byte mirrored (pydantic ↔ zod), with a
  validate step that accepts the example and rejects malformed input.
- **Good test coverage** of the plumbing: ~92 engine tests, ~75 API tests,
  closed-form Black-76 checks, IV convergence, exposure signs, field invariant,
  level extraction, HIRO signing, auth/entitlement/state.
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
> rename the field is a pending HUMAN decision — no code/field rename here.**

With these, every heavy item on the
original backlog is built (all EXPERIMENTAL); what remains is the forward-run
**validation** that would move any of them from "mechanism" to "evidence".

### 3. Live feed is a stub 🔴
`feed/live.py` raises `LiveFeedNotAvailable`. Today only historical replay works.
Real-time is unbuilt.

### 4. Frontend dashboard incomplete 🟡
Heatmap, profiles, levels, and auth exist as primitives. The full integrated
TRACE-style dashboard (`1.png`), the intraday **HIRO line** render, and
end-to-end live-WS wiring are the largest remaining FE work.

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
| 4 | HIRO source | `trades.side` aggressor | ✅ |
| 5 | HIRO in Snapshot | optional field, no version bump | ✅ |

## One-line summary

> The skeleton, muscles, and skin are excellent. What's thin is the **nervous
> system** (a signal proven to mean something) and the **mirror** (a way to check
> it against reality). Build the validation harness next; everything else is
> additive polish on a solid frame.
