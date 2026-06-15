# HIRO accumulator unification (worker ↔ generator parity)

**Status:** APPROVED — implementation in progress
**Date:** 2026-06-15
**Locks affected:** none (additive in api-layer; engine purity preserved)
**Schema impact:** none (snapshot field `hiro` already optional; semantics tighten, contract bytes do not change)

## 1. Problem (FACT)

The live `MinuteWorker._hiro_for` (`services/api/src/api/worker.py:255-275`) re-prices the entire RTH-day tape `[rth_open, ts]` at the single current-minute forward `F_t` every minute via `engine.hiro.hiro_series`. The offline generator (`services/engine/scripts/gen_session_snapshots.py:75-112`) instead carries a persistent `engine.hiro.HiroState` across minutes and feeds only the **NEW suffix** of trades with the per-minute forward.

Result: for the same session, the two paths render **different cumulative HIRO lines** even though they consume the same trade set. The generator's *frozen-increment* semantics is the economically-correct one — a trade's hedging delta-notional is set at the price prevailing **then**, not re-priced as the futures move.

Cited audit: `docs/08-status-and-gaps.md` §4 lines 340-377.

## 2. Goal

The live worker emits the same per-minute HIRO scalar as the generator for any given session, while staying:
- **restart-safe** (worker pod can crash mid-session and resume without HIRO drift),
- **gap-safe** (a feed hiccup ≤30s tolerance must not corrupt cumulative state),
- **engine-pure** (no clock/IO/calendar in `engine.*`; `HiroState` stays dumb).

## 3. Non-goals

- We do NOT push `HiroState` into `build_snapshot` (engine purity locked, `AGENTS.md`).
- We do NOT change the `hiro` snapshot field schema (`HiroSnapshot` already final-only scalar; `cumulative` per-trade path remains generator-only).
- We do NOT add a `trades` Timescale table (none exists; restart recovery uses Redis snapshot + feed adapter replay).
- We do NOT refactor `gen_session_snapshots.py` — generator already correct, parity test pulls it as oracle.

## 4. Design (locked decisions)

### 4.1 State location

Persistent `HiroState` lives in `MinuteWorker` instance, **per instrument**. The api-layer worker is the only place that holds mutable cumulative state — engine stays pure. Field on `MinuteWorker`:

```python
self._hiro_states: dict[str, HiroState] = {}     # instrument -> live accumulator
self._hiro_consumed: dict[str, int] = {}         # instrument -> count of trades already fed
self._hiro_session_date: dict[str, date] = {}    # instrument -> ET date the accumulator covers
```

### 4.2 Increment semantics (matches generator)

Each tick at `ts_utc`:

1. Fetch full window `trades = adapter.get_hiro_trades(instrument, ts_utc)` (returns chronological `[rth_open, ts+1min)` per `engine/feed/historical.py:229-260` — unchanged).
2. Feed only the **NEW suffix** `trades[hiro_consumed[instrument]:]` into `state.add(tr, forward, rate)` using **the current-minute forward** `forward` as `F_k` for those new trades.
3. `hiro_consumed[instrument] = len(trades)`.
4. `hiro = state.snapshot()` → embed in snapshot (`.final` only; no per-trade path).

This freezes each trade's increment at its arrival-minute forward — identical to the generator.

### 4.3 Reset at RTH open (Q1 → option **b**)

Trigger reset when the **first trade of a tick** has `tr.ts >= rth_open_today_et` AND the stored `_hiro_session_date[instrument]` is older than today's ET date (or unset).

- Implemented in a small helper `_maybe_reset_hiro(instrument, ts_utc, trades)` called BEFORE the suffix-feed step.
- Compares ET date of `ts_utc` with `_hiro_session_date[instrument]`; if drift → drop state, recreate `HiroState(MULTIPLIER[instrument])`, reset `hiro_consumed = 0`, set `_hiro_session_date` to today.
- Edge: pre-RTH ticks (PREMARKET branch is idle, so this code path doesn't run) — handled implicitly because `_produce_live` is only called from LIVE/STALE-recovery branches.

Why option (b) over (a) "reset on calendar tick": the worker's clock is the source of session ticks; resetting on `tr.ts >= rth_open` keeps the state aligned to the **trade tape**, not the wall-clock, which survives clock skew across pod restarts.

### 4.4 Mid-session restart recovery (Q2 → option **b** with **a** fallback)

Two-tier recovery on `_produce_live` first invocation post-restart:

**Tier 1 — Redis snapshot (fast path):**
- Worker writes a compact HIRO state dump to Redis once per minute, key `flowdesk:hiro:{instrument}`, value JSON of `{date_et, total, calls, puts, zerodte, retail, skipped, consumed_count}` (~150 bytes).
- TTL = 90 minutes (covers any plausible same-session restart; expires naturally before the next session).
- On worker startup, before first tick of an instrument, attempt restore. If `date_et == today_et` AND `consumed_count <= len(current_trades)` → reseed `HiroState` directly, set `_hiro_consumed = consumed_count`, skip Tier 2.

**Tier 2 — Feed-adapter replay (fallback):**
- If Tier 1 miss (key absent, expired, or date mismatch) → fall back to *naive replay*: leave `HiroState` empty, set `_hiro_consumed = 0`, let the next tick's full window get re-fed from scratch at the **current minute's forward**. This silently degrades to the old (pre-fix) behaviour for that one tick, then converges.
- Mark the snapshot `degraded=true` for that single tick (see §4.5; reuses the gap-degrade flag).

Why two tiers: Tier 1 gives perfect parity post-restart in 99%+ of cases (same-process redis is durable). Tier 2 prevents the worker from dying if Redis is down — degrade gracefully, never crash.

### 4.5 Feed-gap handling (Q3 → option **c**)

When `determine_state` returns `STALE` and the recovery `_produce_live` succeeds (`worker.py:216-219`), the `HiroState` survives the gap untouched — that's correct: no trades arrived during the gap, so the accumulator should not advance, only the cumulative line freezes.

When the gap is **>30s** (the existing `feed_gap_tolerance_s` threshold), an extra flag is added to the snapshot: `degraded=true` (NEW boolean field, additive, defaults `false`). FE-side this powers a "data quality" pip on the HIRO line.

Decision: `degraded=true` is set ONLY on the first recovery tick after a >30s gap, then back to `false`. It does NOT cause any state mutation, just signals "this minute's value crossed a gap".

**Schema delta:** `degraded: Optional[bool] = False` on `Snapshot` model + zod mirror + CONTRACT.md row. Mirror trio update is **atomic** in commit 3 (per locked rules).

> Note on the original Q3 phrasing ("recover from Timescale trades"): rejected — Timescale has no `trades` table (only `snapshots`), so a SQL-replay tier is impossible. Tier 2 fallback in §4.4 replaces it.

## 5. Implementation plan (4 commits)

| # | Scope | Files | Tests |
|---|-------|-------|-------|
| 1 | This design doc | `docs/architecture/hiro-unification.md` | n/a |
| 2 | Engine: confirm/extend `HiroState` API (no semantic change — `add()` already works); add a `to_dict()` / `from_dict()` for Redis snapshot/restore | `services/engine/src/engine/hiro.py`, `services/engine/tests/test_hiro.py` | unit: round-trip `to_dict`/`from_dict` preserves all five lines + skipped + multiplier |
| 3 | Worker: wire persistent `HiroState`, reset-at-RTH-open, Redis snapshot/restore, `degraded` flag on the snapshot model | `services/api/src/api/worker.py`, `services/api/src/api/state.py` (helper for hiro key), pydantic + zod + CONTRACT.md | unit: reset trigger, restart-with-redis, restart-without-redis, gap-degraded flag |
| 4 | Parity test: drive the worker over a fixture session and assert `worker.hiro == generator.hiro` minute-by-minute | `services/api/tests/test_hiro_parity.py` | `pytest -k hiro_parity` green |

## 6. Acceptance

- Parity test in commit 4 green: for the existing fixture session, `worker._tick_instrument` over all 390 RTH minutes produces a `hiro.total` sequence equal (within 1e-9 USD) to the generator's `hiro.total` sequence on the same trade tape.
- Engine test suite still 199 pass.
- API test suite still ≥108 pass + new commit-3 tests + parity test.
- `docs/08-status-and-gaps.md` §4 status flipped DEFERRED → RESOLVED with commit hash.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Worker restart with empty Redis silently produces 1 tick of "wrong" HIRO (Tier 2 fallback) | Snapshot carries `degraded=true` for that tick; FE shows data-quality pip; subsequent ticks converge perfectly. |
| ET date detection drift across pod timezones | Use `pytz`-equivalent (existing `api.session.MarketCalendar.NY_TZ`) — the same source the rest of the worker already trusts. No new tz logic. |
| Redis hiro key bloat | Single string per instrument, ~150 bytes, TTL 90 min → bounded ≤ 2 keys × 150B = 300B steady-state. Negligible. |
| Generator changes in the future, parity test breaks | Parity test pulls generator as oracle — locked behaviour is "worker == generator", so any divergence MUST be resolved before merge. Acceptable maintenance burden. |

## 8. Out of scope

- Re-evaluating HIRO predictive harness (`analysis/harness/hiro_eval.py`) — that path uses generator output, unaffected.
- 0DTE retail classifier refinement (still odd-lot heuristic).
- Multi-replica worker (out of scope for beta; today's deployment is single-replica).
