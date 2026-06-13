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

### 1. No validation / backtest harness — the biggest gap 🔴
The engine computes GEX/DEX/levels that **nobody has tested against reality**:
- Nothing reconciles the synthetic, VOL-based dealer positioning against
  **official ΔOI** (from `statistics`).
- Nothing tests whether /ES-options GEX has **any predictive relationship** to
  /ES price (pinning, flip-level reactions, etc.).
- The golden test only proves **self-consistency**, not correctness.

This is the root cause of "feels done but lacking." Recommended first build:
an offline harness that (a) reconstructs end-of-day dealer position and compares
it to next-day ΔOI, and (b) measures whether price respects gamma-flip / walls
intraday across the 90-day window. **Confirm scope with the human before building
— it's a heavy item.**

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

### 5. Surface / vanna / charm isolated 🟡
`surface.py` (SVI + expected move) and `black76` vanna/charm are implemented and
tested but **not in the Snapshot** and consumed nowhere. No VEX/CHEX aggregation
exists. Wiring them in is additive.

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
