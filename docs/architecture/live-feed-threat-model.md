# LiveAdapter — threat model & deploy rail

**Status:** APPROVED, implemented (rail + minute-assembly complete 2026-06-18; remaining gap: `LiveAdapter.get_ohlc` — live candles degrade to None until wired)
**Date:** 2026-06-15 (status updated 2026-06-22)
**Scope:** the realtime Databento path (`engine/feed/live.py`) + the `FEED_MODE=live` rail in the api worker.

> The Databento account on this project has been locked **twice** in the past
> due to runaway/abusive request patterns. The single most important property
> of this design is therefore: **no code path can flip the worker into
> real-account live mode without an explicit, human-set environment flag.**

## 1. Failure modes the design must defend against

| # | Failure mode | Why it locks the account / costs money | Mitigation |
|---|--------------|-----------------------------------------|------------|
| F1 | Worker silently boots with `FEED_MODE=live` because of a stray env var, .env import, or container default | An always-on subscription racks up minute charges and trips the abuse heuristic when something else then loops the connection | Explicit two-key arming: `FEED_MODE=live` **AND** `LIVE_FEED_ARMED=1`. Either alone refuses to boot with a loud error. |
| F2 | Feed gap → reconnect storm → too many subscriptions per second | Databento abuse heuristic has flagged this pattern before | Reconnect with exponential backoff and a hard cap (5 attempts, max 5 min total) before the circuit breaker opens. Once open, every tick raises `LiveFeedDegraded` → caught → the session goes STALE on the last frame (it does NOT switch to fresh historical replay data). |
| F3 | Bug raises in the per-tick path, worker crashes, k8s restarts it instantly, repeat | Same effect as F2 but on a longer cycle | Outer-loop crash detector: if `_connect()` is called >N times in M minutes, refuse and exit (the human must inspect). |
| F4 | Test/CI somehow imports `databento` and dials home | Even one auth attempt under the wrong context can be flagged | The `databento` import is **lazy and gated**: it lives inside `LiveAdapter._connect()`, which is itself unreachable unless `LIVE_FEED_ARMED=1`. CI sets `FEED_MODE=historical` and a default refuse-flag; the `live` test path uses a hand-rolled `FakeLiveClient` only. |
| F5 | Stale credentials get committed | Account compromise | `DATABENTO_API_KEY` is read from env only. A repo-wide grep for `db-` style keys runs in the pre-deploy checklist. **The `.env*` files stay in `.gitignore` (verified by repo audit).** |
| F6 | Auto-recovery loop driven by some health-check probe | Subscriptions get re-established faster than the budget allows | Once the circuit breaker opens, it never auto-closes: every subsequent tick raises `LiveFeedDegraded` and the session stays STALE on the last frame for the rest of the process lifetime. Re-arming is an explicit human action (restart with `LIVE_FEED_ARMED=1` again). NOTE: the worker does NOT swap `self._feed` to a historical adapter — there is no live→historical data fallback; "degraded" means frozen-STALE, not fresh replay. |
| F7 | Forward / chain assembly bug → the engine sees garbage and the FE shows nonsense numbers to a paying customer | Reputation, refunds | Every minute the live adapter assembles a chain it MUST pass the same `OptionChainMinute` validator the historical path does (locked contract). On validator fail → emit nothing for that minute and surface a STALE → the existing `_republish_stale` path already handles that cleanly. |

## 2. The two-key arming rail (defence against F1, F3, F6)

```text
+---------------------------+   FEED_MODE=live ?
|  worker boot               | ----- no ----> historical adapter
+---------------------------+   yes
            |
            v
   LIVE_FEED_ARMED == "1" ?  ---- no  ----> RuntimeError("LiveAdapter requested but not armed")
            |   yes
            v
   DATABENTO_API_KEY set ?   ---- no  ----> RuntimeError("LiveAdapter armed but no API key")
            |   yes
            v
   build LiveAdapter (does NOT connect yet)
            |
            v
   first tick triggers _connect() — **only here** is a network call made
```

Both keys MUST be present at process boot. Either flips alone:
- `FEED_MODE=live`, `LIVE_FEED_ARMED` unset → refuse with the message
  `LiveAdapter is not armed. Set LIVE_FEED_ARMED=1 to acknowledge real-account contact.`
- `LIVE_FEED_ARMED=1`, `FEED_MODE=historical` → no-op (the flag is never read).

The arming flag is **NOT** documented in the public README; it lives only in
the deploy runbook so an operator cannot enable it accidentally by skimming
docs.

## 3. Circuit breaker (defence against F2)

The adapter tracks `_consecutive_failures`. After **N=5 consecutive failures**
within a **rolling 5-minute window**, the breaker **OPENS**:

- `_connect()` raises `LiveFeedDegraded` with a final structured log line:
  `live_feed.breaker.opened consecutive_failures=5 window_seconds=300`.
- The worker's `_produce_live` catches feed exceptions (the broad `except
  Exception` at `worker.py:509-513`) and holds the last frame; once the gap
  exceeds tolerance the session reports STALE via `_republish_stale`. Because
  the breaker never auto-closes, `LiveFeedDegraded` is raised on EVERY
  subsequent tick, so the session stays STALE on the last live frame for the
  rest of the process lifetime.
- IMPORTANT: the worker does NOT swap to a historical adapter. `self._feed` is
  assigned once at construction (`worker.py:151`) and never reassigned; there
  is no `_feed_mode_effective` flag. "Degraded" therefore means frozen-on-last-
  frame STALE, NOT a switch to fresh historical replay data. Recovery requires a
  human restart.

A single human restart resets the breaker; there is no automatic close.

## 4. Reconnect policy (defence against F2)

Within a single `_connect()` call:

- Backoff: `min(2 ** n, 60)` seconds between retries.
- Max retries per `_connect()` call: **5**.
- Total wall-time cap per `_connect()` call: **5 minutes**.

When the cap is hit `_connect()` raises and increments
`_consecutive_failures`.

## 5. Crash-loop detector (defence against F3)

A small file `~/.flowdesk/live-arm-attempts.log` (configurable path) records
each successful arm. If more than **3 arms in 10 minutes** are observed at
process boot, the worker refuses to start and the operator must clear the
log. This catches the Kubernetes-restart-storm scenario: a crash followed
by an immediate restart re-runs `_connect()` faster than the
within-process backoff above.

## 6. Test discipline (defence against F4)

- Unit tests **never** import `databento`. The `import databento` line is
  inside `_connect()`, behind the arming check, behind `FEED_MODE=live`.
- The `LiveAdapter` test suite replaces the realtime client with a
  hand-rolled `FakeLiveClient` that yields recorded definitions / trades /
  bbo records inline — the parser and per-minute book code paths are
  exercised, but no socket is opened.
- CI explicitly sets `FEED_MODE=historical` and `LIVE_FEED_ARMED=` (empty).
- Any test that needs to drive the arming rail uses
  `monkeypatch.setenv("LIVE_FEED_ARMED", "1")` scoped to a single test
  function — never via a session-wide fixture.

## 7. What this design intentionally does NOT do

- **No automatic re-arm.** Once the breaker opens, a human must restart.
- **No "healthy live for testing" sandbox key in CI.** Sandbox keys still
  count as a real account contact for Databento's heuristics.
- **No `degraded=true` flag on the snapshot contract** (would touch the
  locked Snapshot mirror trio; the existing WARNING log + the worker's
  `state="STALE"` field already convey the operational signal).
- **No paper-trade / replay-into-live blend mode.** Either it's live, or
  it's historical; nothing in between, by design.

## 8. Pre-deploy checklist (operator)

Before flipping `LIVE_FEED_ARMED=1` on any environment:

1. Confirm `DATABENTO_API_KEY` is populated from a secret manager (not a `.env*` file in the image).
2. `git grep -E 'db-[A-Za-z0-9]{8,}' --` returns no matches in tracked files.
3. The arm-attempts log is empty or clean.
4. The Databento dashboard shows the account is in good standing.
5. Page the on-caller before arming; the first 30 minutes must be supervised.

## 9. Implementation map (Phase 3 commits)

| # | Step | Files | Tests |
|---|------|-------|-------|
| 1 | This doc | `docs/architecture/live-feed-threat-model.md` | n/a |
| 2 | Live adapter scaffolding: arming check, lazy-import gate, circuit breaker, backoff, FakeLiveClient seam | `services/engine/src/engine/feed/live.py` | unit: arming refuse, breaker opens after N failures, backoff capped |
| 3 | Two-key rail at the wiring site: refuse-by-default in `make_adapter` + `build_worker_from_env` | `services/engine/src/engine/feed/__init__.py`, `services/api/src/api/worker.py` | unit: env-matrix coverage of (FEED_MODE × LIVE_FEED_ARMED × DATABENTO_API_KEY) |
| 4 | Test suite | `services/engine/tests/test_live_adapter.py`, `services/api/tests/test_feed_mode_rail.py` | full matrix, parity-light (FakeLiveClient → same `OptionChainMinute` shape as historical) |

## 10. Acceptance

The Phase 3 fix-set is done when:
- `pytest services/engine/tests/test_live_adapter.py services/api/tests/test_feed_mode_rail.py` is green.
- A grep across the full repo confirms `import databento` only appears under
  `analysis/` (research scripts, network-permitted by definition),
  `engine/feed/live.py` (gated), and `engine/scripts/ingest_databento.py`
  (also gated).
- Booting the worker with `FEED_MODE=live` but no `LIVE_FEED_ARMED` raises
  a loud `RuntimeError` *before* any network call.
