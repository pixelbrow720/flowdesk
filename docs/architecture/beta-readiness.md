# Beta readiness audit — backend

**Audit date:** 2026-06-15
**Scope:** the FlowDesk backend (`services/engine`, `services/api`,
`packages/contracts`, `analysis/harness`) + supporting docs.
**Question:** is the backend ready to ship to **paying beta users** as a
0DTE GEX/DEX terminal for /ES and /NQ, on the historical-replay path?
**Verdict:** **GO for paid beta on `FEED_MODE=historical`.**
LiveAdapter is built but stays disarmed in beta until the operator
checklist runs (the second arming key is intentionally absent in the
beta image).

---

## 1. What this audit covers

- The 12 hardening commits since baseline `b3c2ae0` (Phase 1 + Phase 2
  + Phase 3, see §6 "Commit ledger").
- The locked Snapshot contract integrity (schema_version, mirror trio).
- Auth / CORS / rate-limit / finiteness boundary hardening.
- FLUX unification (worker ↔ offline generator parity).
- LiveAdapter safety rail (the two-key arming gate, circuit breaker,
  test isolation).
- Secrets posture (.env*, tracked files, env inventory).
- Test posture (engine + api suites, full coverage of the new code).
- Outstanding deferred items + their risk classification.

This audit does NOT re-validate the experimental research lenses (DDOI,
SVI / expected-move, synthetic-OI, total-hedging, vanna/charm). They
remain `EXPERIMENTAL / NOT-VALIDATED` per
`docs/08-status-and-gaps.md`; the FE will surface them with their
honesty labels intact when the FE is rebuilt.

## 2. Audit findings

### 2.1 Locked contract integrity ✅ PASS

- `schema_version=1` is preserved across every commit landed in this
  build.  Confirmed by `git grep "schema_version" docs/03-data-contract.md`
  + the `SchemaVersion = 1` constant in `packages/contracts/`.
- The mirror trio (`schema.py` ↔ `snapshot.ts` ↔ `CONTRACT.md`) was not
  touched by this hardening pass — every Phase 2/3 change is at the
  worker / state-store / feed-adapter layer, behind the Snapshot
  boundary. (The FLUX cumulative-VOL fix changed *what numbers*
  populate the existing `flux` field, never the field's shape.)
- Engine purity preserved: `build_snapshot` still has no clock / IO /
  calendar dependency. Persistent `FluxState` lives **only** in
  `services/api/src/api/worker.py:MinuteWorker`, never in
  `services/engine/src/engine/snapshot.py`. Verified by re-reading the
  Phase 2 design doc (`docs/architecture/flux-unification.md`) against
  the four landed commits.

### 2.2 Auth / CORS / rate-limit / finiteness ✅ PASS

| Surface | Hardening | Test |
|---------|-----------|------|
| CORS | refuses `*`+credentials, refuses non-https/non-localhost (`api/main.py:65–`, `api/auth.py:90–`) | `services/api/tests/test_auth.py`, `test_me_contract.py` |
| Rate limit | Redis-backed token bucket on `/api/me/recheck`, OAuth callback, WS handshake; wired BEFORE auth/CSRF; fail-open on Redis hiccup; WS close code 4429 | `services/api/tests/test_rate_limit*.py` (covered) |
| Finiteness | pydantic ingress + zod egress validators reject NaN / Inf in Snapshot at both boundaries | `services/api/tests/test_*finite*` (covered) |
| Cookies | `HttpOnly` + `Secure` (unless `COOKIE_INSECURE=1` for local dev) + `SameSite=Lax`, 7d TTL (`api/auth.py:82`) | `test_auth.py` |
| Session | HMAC-signed via `SESSION_SECRET` env (`api/security.py:39`); validator refuses missing/empty | covered |

No regressions from these on the engine or contract suites.

### 2.3 FLUX unification ✅ PASS (Phase 2 RESOLVED)

- `engine/flux.py` `FluxState` is the single source of truth for
  cumulative dealer delta-notional since RTH open.
- Worker (`api/worker.py:MinuteWorker._hiro_for`) holds persistent state
  per-instrument; feeds only the NEW suffix at each minute's `F_t`
  (freeze-at-arrival semantics).
- Two-tier restore: Tier-1 Redis snapshot per tick (TTL 5400s) /
  Tier-2 fresh accumulator on miss/wrong-date/malformed/Redis-error.
- Daily ET reset on session-date rollover; defensive shrunken-window
  detection guards against fixture rebuild.
- **Parity test**: `test_hiro_parity.py` asserts worker output is
  bit-equal (≤1e-9 abs diff) to `gen_session_snapshots.py:75-112` over
  a 6-min scripted session. Was the open defect from the
  2026-06-14 quant-greeks-auditor pass; now closed.

### 2.4 LiveAdapter safety rail ✅ PASS (Phase 3 RESOLVED)

- **Two-key arming gate** (the central anti-account-lock control):
  `make_adapter("live")` refuses with `LiveFeedNotArmed` unless
  `LIVE_FEED_ARMED=1` is set. `FEED_MODE=live` alone, or an inherited
  env, cannot reach real-account contact.
- **Lazy gated `import databento`**: only inside `_open_client()`,
  behind the arming check, behind the `client_factory` test seam.
  Verified by `test_module_does_not_eagerly_import_databento`.
- **Circuit breaker**: 5 consecutive failures in a 5-minute rolling
  window opens the breaker permanently for the process lifetime;
  subsequent calls raise `LiveFeedDegraded`. No automatic close.
- **Bounded reconnect**: max 5 attempts per `_connect()`, exponential
  backoff capped at 60s, 5-minute total wall budget.
- **Loud boot log**: `build_worker_from_env` logs `feed_mode` and
  `live_armed` as a WARNING so an operator can spot a misconfigured
  live flip immediately.
- **Beta posture**: the beta image will ship with `FEED_MODE=historical`
  AND `LIVE_FEED_ARMED` deliberately absent. Live-feed activation is
  out-of-band, gated by the operator runbook (see
  `docs/ops/deploy-runbook.md`).
- **Test isolation**: 13 dedicated tests, all mocked via
  `FakeLiveClient`; engine 415 passed; **no CI path imports the real
  `databento` package**.

### 2.5 Secrets posture ✅ PASS

- `git ls-files | grep '^\.env'` returns **only** `.env.example`, which
  carries `db-xxxxxxxxxxxxxxxxxxxxxxxx` placeholder (regex match, not a
  live key).
- `.gitignore` enforces `.env`, `.env.*`, with `!.env.example` allowance.
- Repo-wide grep for live-token shapes (`db-[A-Za-z0-9]{8,}`,
  `sk-[A-Za-z0-9]{16,}`) finds zero hits in tracked files.
- All 8 production secrets read from `os.environ` only:
  `SESSION_SECRET`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`,
  `DISCORD_GUILD_ID`, `DISCORD_DESK_ROLE_ID` /
  `DESK_ROLE_ID`, `DATABENTO_API_KEY`, `TIMESCALE_DSN`, `REDIS_URL`.
- Operational ENV knobs (Pilihan A locked):
  `FEED_MODE`, `LIVE_FEED_ARMED`, `DATA_DIR`, `SOFR_RATE`,
  `QUOTE_SCHEMA`, `CORS_ORIGINS`, `PUBLIC_BASE_URL`,
  `COOKIE_INSECURE`, `RATE_LIMIT_*`, `WS_HEARTBEAT_S`,
  `MOCK_ACCESS_STATE`, `MOCK_RECHECK_STATE`, `DISCORD_JOIN_URL`. All
  have safe defaults; none are hot-path.

### 2.6 Test posture ✅ PASS

| Suite | Count | Status |
|-------|-------|--------|
| `services/engine/tests` | **415 passed** | green |
| `services/api/tests` | **116 passed** | green |
| Concurrent collection | known import-collision in `services/engine/test_repo.py` (sys.path issue with `gen_fixture`) | run suites separately — no functional regression |

Coverage of new code:
- `engine/flux.py` FluxState round-trip — 12 unit tests in
  `test_hiro.py`.
- `api/worker.py` FluxState wiring — 6 unit tests in
  `test_worker_hiro.py` (Tier-1, Tier-2, daily reset, persistence).
- `api/worker.py` ↔ `gen_session_snapshots.py` parity — 2 tests in
  `test_hiro_parity.py` (≤1e-9 abs diff).
- `engine/feed/live.py` — 13 tests in `test_live_adapter.py`
  (arming gate, breaker, backoff, retry budget, no-databento-import
  invariant) + 2 updated tests in `test_historical.py`.

### 2.7 Outstanding items (deferred, classified) 🟡 ACCEPTABLE

| Item | Risk | Rationale |
|------|------|-----------|
| LiveAdapter minute-assembly logic (definition + OI + cumulative VOL + top-of-book mid wired to the realtime stream) | **LOW** | Beta ships on `historical`; the assembly code can land in a follow-up PR with recorded fixtures, gated by the same arming rail. |
| On-disk crash-loop arm-attempts log (F3 layered defence) | **LOW** | The in-process breaker + the explicit second arming key already cover the Kubernetes-restart-storm case at the orchestrator level. Documented in §5 of the threat model for future hardening. |
| Concurrent `pytest engine api` collection | **NEGLIGIBLE** | Pre-existing sys.path quirk in `test_historical.py` import of `gen_fixture`. Suites run cleanly when invoked separately. CI runs them separately by design. |
| 14 in-source TODO/FIXME tags (mostly `analysis/harness/provenance.py`) | **LOW** | Research-side; not on the hot path. None in `services/engine/src/engine/snapshot.py` or `services/api/src/api/`. |
| Experimental research lenses still `NOT-VALIDATED` | **OUT OF SCOPE for this audit** | Honesty labels travel with the snapshot fields by contract. The FE will surface them as `EXPERIMENTAL`. |

## 3. Beta-launch go/no-go matrix

| Gate | Status | Notes |
|------|--------|-------|
| Engine purity (no clock/IO/calendar) | ✅ | preserved |
| Locked Snapshot contract (schema_version=1, mirror trio atomic) | ✅ | not touched |
| Auth / CORS / rate-limit / finiteness | ✅ | hardened in Phase 1 |
| FLUX bit-equality vs offline generator | ✅ | parity test ≤1e-9 |
| LiveAdapter cannot accidentally contact real account | ✅ | two-key arming + lazy gated import + breaker |
| Secrets out of source control | ✅ | `.env*` ignored, no live tokens tracked |
| Test suites green | ✅ | 415 + 116 |
| Operator runbook for deploy / arm-live / rollback | ✅ | `docs/ops/deploy-runbook.md` (Phase 4 commit 3) |
| Snapshot finiteness at egress (FE will not see NaN/Inf) | ✅ | zod boundary validator |
| Rate-limit-induced failure modes (WS close 4429) | ✅ | covered |

**Verdict:** all 10 gates pass → **GO for paid beta on
`FEED_MODE=historical`**.

The beta image is operationally a "historical-replay terminal": users
get the locked Snapshot contract, real auth + CORS + rate-limit, and
the experimental lenses with their honesty labels. Live-feed flip is a
follow-up event gated by the runbook.

## 4. What gets re-audited before the LIVE flip

When the operator decides to flip a single environment to
`LIVE_FEED_ARMED=1`:

1. Re-run the full pre-deploy checklist in
   `docs/architecture/live-feed-threat-model.md` §8.
2. Verify the actual minute-assembly logic is in (or behind a feature
   flag).
3. Page the on-caller; the first 30 minutes of live operation must be
   supervised.
4. Confirm circuit-breaker tripping behavior on the staging environment
   (forced-failure synthetic test).

Until that day, the LiveAdapter stays disarmed in production.

## 5. Sign-off

This audit is INLINE (no external auditor available). The audit is
backed by:
- The four landed Phase 2 commits + the five landed Phase 3 commits
  with full mocked test coverage.
- The FLUX bit-equality parity test (`test_hiro_parity.py`).
- The threat-model doc (`docs/architecture/live-feed-threat-model.md`).
- The operator runbook (`docs/ops/deploy-runbook.md`).

The product is appropriate for **paid beta on historical replay**,
with the honesty labels on experimental lenses preserved.

## 6. Commit ledger (since baseline `b3c2ae0`)

```
a611ac4 docs(08): mark live feed RESOLVED                     (P3 c5)
69d7893 test(engine): LiveAdapter mocked unit tests           (P3 c4)
c46cb20 feat(api,engine): refuse-by-default rail FEED_MODE    (P3 c3)
37e7a03 feat(engine): LiveAdapter arming gate + breaker       (P3 c2)
dca4e9f docs(architecture): LiveAdapter threat model + rail   (P3 c1)
bf185cf docs(08): mark FLUX unification RESOLVED              (P2 c5)
8097228 test(api): FLUX worker<->generator parity             (P2 c4)
4b97756 feat(api): wire persistent FluxState in MinuteWorker  (P2 c3)
445e019 feat(engine): FluxState.to_dict/from_dict             (P2 c2)
604bad5 docs(architecture): FLUX unification design           (P2 c1)
04c29dd feat(api): rate-limit /me/recheck, OAuth, WS          (P1 i2)
7ef0abc feat(api,engine): CORS validation + Snapshot finite   (P1 i1+i4)
```

12 commits. Engine 415 passed (was 401 at FLUX start). API 116 passed.
