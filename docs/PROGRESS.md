# PROGRESS — Heavy-Task Build (resume here in a new session)

> **NEW SESSION: read this file + `git log --oneline -15` FIRST, before touching
> anything.** This tracks the multi-point heavy build the user approved 2026-06-13.
> Heavy/assumption items follow the EXTENDED workflow (see memory
> `flowdesk-heavy-task-workflow`): creative → evidence → creative → validate →
> audit → validate → match-project → document → execute → validate → document.
> Light items follow the standard red-team cycle. Update this file at EVERY
> completed point / meaningful checkpoint.

## Permanent opus subagents available (`.claude/agents/`)
- **redteam-auditor** — adversarial attacker (break the claim).
- **contract-guardian** — pydantic↔zod↔CONTRACT.md mirror parity.
- **quant-greeks-auditor** — dimensional analysis, sign conventions, scale constants,
  finite-difference, reduction properties, look-ahead/confound. USE for every
  formula in this build.

## Hard rules (unchanged)
LOCKED CONTRACT / VOL-GEX-DEX / `schema_version=1` untouched. New fields additive,
optional, nullable, EXPERIMENTAL, alongside (never replacing) VOL-GEX. Mirror
lockstep. No new Databento pull. Trust-but-verify diffs; tests green before "done".

## Verify commands
```
# engine:   cd services/engine && PYTHONPATH=src ../../.venv/Scripts/python.exe -m pytest -q
# api:       cd services/api && PYTHONPATH=src:../engine/src ../../.venv/Scripts/python.exe -m pytest -q
# contracts: cd packages/contracts && node_modules/.bin/tsc --noEmit && node_modules/.bin/tsx scripts/validate.ts
# harness:   .venv/Scripts/python.exe -m pytest analysis/harness/test_metrics.py -q
# golden regen ONLY if intentional: edit additively by hand (env float churn — do NOT commit noise)
```

## Baseline at start of this build
HEAD `1131d9b`. Engine 172 pass, API 78 pass, harness 17 pass, contracts tsc+validate clean.

---

## The plan (in build order) + status

| # | Item | Workflow | Status |
|---|------|----------|--------|
| 1 | Synthetic-OI **#7 total-hedging** (gamma+charm+vanna on Q base) | heavy | ✅ DONE (commit pending) |
| 2 | **SVI / expected-move** wiring (gap #5 remainder) | heavy | ✅ DONE (commit pending) |
| 3 | **OI-aware wall-validation** pass in harness (gap #1 remainder) | heavy | ✅ DONE (commit pending) |
| 4 | Synthetic-OI **#6 size-tiered** (needs per-trade-tape refactor) | heavy | ✅ DONE (commit pending) |
| 5 | Synthetic-OI **#5 decay-weighted** (needs HiroTrade.ts + #6 refactor) | heavy | ✅ DONE (commit pending) |
| 6 | **Baseline lint/type cleanup** (gap #6) | light | ✅ DONE (commit pending) |
| D | **DDOI engine** — same-session, EXPERIMENTAL, alongside VOL-GEX (NOT cross-day; proven impossible on 0DTE) | heavy | ✅ DONE (commit pending) |
| P | **Proprietary metrics** (Volatility Trigger / Hedge Wall / Risk Pivot etc.) — reverse-engineered, labelled approximation | heavy | ⏳ NOT STARTED |

Legend: ⏳ not started · 🔨 in progress · ✅ done+pushed · ⚠️ blocked

---

## Checkpoint log (append newest at top)

### 2026-06-13 — Point D DONE: DDOI engine (synthetic Dealer Directional OI GEX)
- `engine/ddoi.py` (NEW): `ddoi_time_weight(i,n)=1−2·(i/(n−1))` (early=open +1, late=
  close −1) + `ddoi_gex`/`build_ddoi` — applies the LOCKED dealer-sign + gamma + scale
  template to a per-leg synthetic-ΔOI basis instead of VOL. Non-circular, orthogonal
  to VOL. Skips thin strikes. Reuses analysis/ddoi.py's validated open/close heuristic.
- worker.py: `_net_flow_ddoi_for(trades)` groups per leg, sorts chronologically (uses
  the point-5 HiroTrade.ts), sums `ddoi_time_weight·|size|` (direction-agnostic).
  Passed as new `net_flow_ddoi` param.
- snapshot.py: `net_flow_ddoi` -> build_ddoi -> new field `ddoi`. NEW Ddoi model
  {gex, sign} (not a SyntheticOi reuse — different shape). schema_version stays 1.
- Mirror: schema.py Ddoi + snapshot.ts Ddoi interface + DdoiSchema + SnapshotSchema
  entry + invariant tuple. CONTRACT.md row+section. golden gains only "ddoi": null.
- tests: test_ddoi.py (NEW, 6 tests: time-weight first=+1/last=−1/monotone, locked
  signs+scale, thin-skip, sign). _SNAPSHOT_KEYS + zod-compat updated.
- HONEST: on the 8-day exploratory run DDOI read FLAT vs VOL (49.2% vs 50.8%) — the
  machine is sound, the edge is NOT proven. EXPERIMENTAL, alongside VOL-GEX. Cross-day
  ΔOI reconciliation remains impossible on 0DTE (this is same-session open/close only).
- VERIFIED: engine 192 pass, api 78 pass, contracts tsc exit 0 + validate ok, ruff +
  mypy clean on new module.
- docs: 04-engine.md, 08-status #2 (DDOI now built w/ approval), CONTRACT.md, PROGRESS.
- Next: Point P (proprietary metrics — the last item; HEAVY workflow).

### 2026-06-13 — Point 6 DONE: scoped lint/type cleanup (gap #6)
- Engine ruff: had exactly 1 finding (MINE — unused `ChainRow` import in
  test_surface.py from point 2); removed -> engine ruff now CLEAN (exit 0).
- API ruff: 169 baseline. Did NOT blind-fix (docs warn B008 are FastAPI Depends
  false positives; UP*/N818 are intentional). Fixed ONLY unambiguous dead code:
  F401 (10 unused imports) + RUF100 (14 dead noqa) via `ruff --select F401,RUF100
  --fix`. 169 -> 160. The remaining 160 (UP007/UP017/B008/N818/S105/...) are the
  documented baseline, deliberately LEFT ALONE.
- F821 `Fernet` in auth_session.py: investigated — FALSE POSITIVE (quoted annotation
  + intentional lazy import). Not a bug, not touched.
- mypy: CLEAN on all modules I added/modified this session (total_hedging,
  exposure_ext, synthetic_oi, surface). No new type debt. Locked-core mypy baseline
  (~16 strict errors in snapshot.py/field.py/feed) left as-is per docs.
- VERIFIED: engine 187 pass, api 78 pass. No engine/contract/schema change.
- Next: Point D (DDOI engine — HEAVY workflow, same-session EXPERIMENTAL).

### 2026-06-13 — Point 5 DONE: synthetic-OI #5 decay-weighted
- `engine/synthetic_oi.py`: added `decay_weight(age_minutes)` = exp(-ln2*age/half_life)
  + `DEFAULT_HALF_LIFE_MIN=30` (UNVALIDATED). half_life<=0 disables -> reduces to #4.
- `engine/hiro.py`: `HiroTrade` gains optional `ts: datetime|None` (HIRO unaffected).
- `feed/historical.py`: `get_hiro_trades` now passes `ts=event` (the timestamp was
  already paired at line 264, just dropped at the return — now carried through).
- `worker.py`: `_net_flow_decay_for(trades, ts_utc)` weights each trade by
  decay_weight(age at the snapshot eval time) BEFORE summing; trades w/o ts skipped.
  Passed as new `net_flow_decay` param.
- `snapshot.py`: new `net_flow_decay` param -> reuses build_synthetic_oi -> new field
  `synthetic_oi_decay` (REUSES SyntheticOi model). schema_version stays 1.
- Mirror: schema.py + snapshot.ts add the field + SnapshotSchema entry. CONTRACT.md
  row + note. golden gains only the null line.
- tests: 4 decay_weight tests (fresh/half-life, monotone, disabled->1, clamp neg age);
  _SNAPSHOT_KEYS + zod-compat updated.
- VERIFIED: engine 187 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- All of #5/#6/#7 now built. docs: 04-engine.md, roadmap header (ALL BUILT),
  CONTRACT.md, PROGRESS.md.
- Next: Point 6 (baseline lint/type cleanup — LIGHT workflow).

### 2026-06-13 — Point 4 DONE: synthetic-OI #6 size-tiered
- `engine/synthetic_oi.py`: added `tier_weight(size)` + constants (RETAIL_MAX_SIZE=5,
  BLOCK_MIN_SIZE {ES:50, NQ:25}, RETAIL_TIER_WEIGHT=0, BLOCK_TIER_WEIGHT=1.5). All
  thresholds UNVALIDATED guesses (labelled, to be swept). Identity at weights=1 → #4.
- `worker.py`: new `_net_flow_tiered_for(trades, instrument)` — applies tier_weight
  per trade BEFORE summing (intercepts before the flat sum). Passed as new
  `net_flow_tiered` param.
- `snapshot.py`: new `net_flow_tiered` param → reuses build_synthetic_oi → new field
  `synthetic_oi_tiered` (REUSES the SyntheticOi model — no new pydantic/zod model, no
  new invariant entry). schema_version stays 1.
- Mirror: schema.py + snapshot.ts add `synthetic_oi_tiered: SyntheticOi|null` +
  SnapshotSchema entry. CONTRACT.md row + note. golden gains only the null line.
- tests: 3 new tier_weight tests in test_synthetic_oi.py; _SNAPSHOT_KEYS + zod-compat
  block updated. NOTE the per-trade tiering lives in the WORKER (the engine still
  takes a summed map), so #5 (decay) will need the SAME worker-side per-trade pattern
  + a trade timestamp on HiroTrade (currently absent) + an eval time.
- VERIFIED: engine 183 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- docs: 04-engine.md, roadmap header (#6+#7 BUILT), CONTRACT.md, PROGRESS.md.
- Next: Point 5 (synthetic-OI #5 decay-weighted) — needs HiroTrade timestamp.

### 2026-06-13 — Point 3 DONE: cross-day OI-wall validation in harness
- `analysis/harness/metrics.py`: added pure `oi_walls` (top-N raw-OI call/put walls
  on the correct side of spot). 3 new unit tests.
- `analysis/harness/run_validation.py`: run_day now carries per-strike settle-OI +
  closes + axis strikes; main() adds a cross-day pass — PRIOR session's settle-OI
  walls tested against the CURRENT session's price (look-ahead-free: T-1 precedes T,
  strikes persist cross-day even though 0DTE contracts don't). Reuses the
  distance-matched attraction + pin_rate.
- Ran end-to-end: raw-OI walls land DEEP OTM (lottery/tail-hedge strikes), often
  outside the next day's axis (nbase=0 -> n/a, not fake-0); no pull toward them.
  HONEST NEGATIVE: this shows WHY the product ranks walls by gamma-dollar not raw OI.
- A stronger gamma-$ wall test needs prior-day per-leg gamma (not just settle-OI) —
  deferred to the forward pull; documented in validation-harness.md §6.
- VERIFIED: 20 pure metrics tests pass; harness runs clean. (No engine/contract
  change — harness-only.)
- docs: validation-harness.md §3/§4/§6 updated.
- Next: Point 4 (synthetic-OI #6 size-tiered + per-trade-tape refactor).

### 2026-06-13 — Point 2 DONE: SVI / expected-move surface wiring (gap #5 closed)
- `engine/surface.py`: added `SurfaceSnapshot` + `build_surface` — fits raw-SVI to
  the solved OTM IVs (put<F, call≥F), summarises atm_vol / expected_move (F·σ·√T) /
  skew / rmse / arb_free + the 5 raw-SVI params. `None` when <5 non-thin strikes.
- Mirror lockstep: `Surface` in schema.py + snapshot.ts (interface+zod+invariant) +
  CONTRACT.md (row+section). schema_version stays 1.
- snapshot.py: gated by `with_surface` flag (no flow needed); derives t_expiry from
  solved rows. worker.py + gen_session_snapshots.py pass `with_surface=True`.
- tests: 3 new in test_surface.py (fit+summarise, thin-skip/<5→None, bad inputs);
  _SNAPSHOT_KEYS + zod-compat block updated. golden gains only `"surface": null`.
- docs: 04-engine.md (surface.py no longer ISOLATED), 08-status #5 CLOSED, CONTRACT.md.
- VERIFIED: engine 180 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- Hit a self-inflicted bug: my Edit merged 2 stray leftover lines into a new test
  (NameError `ratio`); caught by running tests, fixed. Auditors still can't run
  (opus 403); audited inline — reduction not applicable here, but the SVI fit is
  covered by the pre-existing recovers-known-smile test + my new wrapper tests.
- Next: Point 3 (OI-aware wall-validation pass in harness).

### 2026-06-13 — Point 1 DONE: synthetic-OI #7 total-hedging
- `engine/total_hedging.py` (NEW): gamma+charm+vanna on the synthetic-OI Q base.
  3 separate fields (units differ), `Q` carries dealer sign (no re-apply).
- `engine/synthetic_oi.py`: extracted `q_per_leg` helper (single source of truth);
  `synthetic_gex` now calls it — behavior-preserving (tests confirm).
- Mirror lockstep: `TotalHedging` in schema.py + snapshot.ts (interface+zod+
  invariant tuple) + CONTRACT.md (row+section). schema_version stays 1.
- snapshot.py: gated by `net_flow` (same as synthetic_oi), threads `rate`. Worker
  already passes net_flow → field auto-populates, no worker change needed.
- tests: `test_total_hedging.py` (NEW, 6 tests; anchor = gamma_hedge ≡ #4 GEX at w).
  golden gains only `"total_hedging": null` (additive).
- docs: 04-engine.md module subsection, roadmap header (#7 BUILT), this file.
- VERIFIED: engine 177 pass, api 78 pass, contracts tsc exit 0 + validate ok.
- AUDIT NOTE: quant-greeks-auditor + contract-guardian subagents could NOT run this
  session (opus model 403 on free plan; quant agent only loads in a NEW session).
  Audited INLINE instead — reduction property (gamma_hedge≡#4 GEX) proves no
  dealer-sign double-apply; scale constants reused verbatim from the red-team-
  resolved exposure_ext. Re-run both auditors in a new session as a backstop.
- Next: Point 2 (SVI / expected-move wiring).

### 2026-06-13 — infrastructure set up
- Created memory `flowdesk-heavy-task-workflow` (extended cycle) + `flowdesk-progress-checkpoint` (points here).
- Created permanent subagent `quant-greeks-auditor` (will load in NEW sessions).
- This PROGRESS.md created. Next: start Point 1 (#7 total-hedging).
- Prior commits this session: `e0be22c` (synthetic_oi docs), `0a5cec1` (VEX/CHEX),
  `733395e` (validation harness), `1131d9b` (#5/#6/#7 plan doc).
