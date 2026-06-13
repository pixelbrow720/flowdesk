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
pass and is deferred** (settle-OI at the open would be look-ahead).

### 2. The GEX core is the naive version 🔴 (decided, but know its limits)
`exposure.py` uses **cumulative VOL × a hardcoded static dealer sign**
(`+1` call / `-1` put). This is intentional (decision #1) and locked, but it is
the weakest methodology:
- Aggressor side ≠ customer side; a static sign cannot capture real dealer
  inventory.
- Cumulative volume double-counts round-trips and has no position decay.

A first **synthetic-OI signed-flow-update lens now exists** — `synthetic_oi.py`,
wired as the **optional, EXPERIMENTAL** `synthetic_oi` Snapshot field (OI-anchored
position updated by native aggressor flow, weight `w∈[0,1]`). It lives **alongside**
VOL-GEX, does **not** replace it, and is **not price-validated** (structural check
on a 4-day sample only) — so it does **not** close gap #1. A full **DDOI** /
ΔOI-reconciled reconstruction is still **not built** (no `ddoi` engine file); the
methodology research marks DDOI as the "inti gap metodologi" and defers it to v3.
**Do not rip out VOL-GEX; do not build DDOI without approval.** When validation
(#1) exists, both synthetic-OI and DDOI become parallel, measurable layers to
compare against VOL-GEX.

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
