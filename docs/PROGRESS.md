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
| 2 | **SVI / expected-move** wiring (gap #5 remainder) | heavy | ⏳ NOT STARTED |
| 3 | **OI-aware wall-validation** pass in harness (gap #1 remainder) | heavy | ⏳ NOT STARTED |
| 4 | Synthetic-OI **#6 size-tiered** (needs per-trade-tape refactor) | heavy | ⏳ NOT STARTED |
| 5 | Synthetic-OI **#5 decay-weighted** (needs HiroTrade.ts + #6 refactor) | heavy | ⏳ NOT STARTED |
| 6 | **Baseline lint/type cleanup** (gap #6) | light | ⏳ NOT STARTED |
| D | **DDOI engine** — same-session, EXPERIMENTAL, alongside VOL-GEX (NOT cross-day; proven impossible on 0DTE) | heavy | ⏳ NOT STARTED |
| P | **Proprietary metrics** (Volatility Trigger / Hedge Wall / Risk Pivot etc.) — reverse-engineered, labelled approximation | heavy | ⏳ NOT STARTED |

Legend: ⏳ not started · 🔨 in progress · ✅ done+pushed · ⚠️ blocked

---

## Checkpoint log (append newest at top)

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
