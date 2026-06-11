# AGENTS.md — Operating Manual for AI Agents working on FlowDesk

> This is the **single source of truth for any AI agent** (Claude Code, Cursor, etc.)
> working in this repo. Read this file top-to-bottom before touching anything.
> Human-oriented documentation lives in [`docs/`](docs/README.md); this file is the
> agent contract.

---

## 0. What FlowDesk is (one paragraph)

FlowDesk is a real-time **0DTE GEX/DEX options terminal** for **/ES & /NQ** CME
futures options. A Python compute engine prices the option chain (Black-76) and
emits **one canonical `Snapshot` per instrument per minute**; a FastAPI service
serves those snapshots over REST/WebSocket behind Discord-role auth; a Next.js
app renders the heatmap + exposure profiles. Everything revolves around the
`Snapshot` data contract (`schema_version` 1).

## 1. Read-before-you-work (in this order)

1. This file (`AGENTS.md`).
2. [`docs/02-locked-contract.md`](docs/02-locked-contract.md) — the LOCKED CONTRACT. Non-negotiable.
3. [`docs/01-architecture.md`](docs/01-architecture.md) — how the pieces fit.
4. [`docs/04-engine.md`](docs/04-engine.md) — the compute core (where most logic lives).
5. [`docs/08-status-and-gaps.md`](docs/08-status-and-gaps.md) — the **honest** map of what is real vs. stubbed vs. naive. **This is your task map.**
6. [`docs/10-acceptance-and-testing.md`](docs/10-acceptance-and-testing.md) — the T-01…T-10 gate. A regression here is a hard blocker.

## 2. Golden rules (do NOT violate without explicit human approval)

1. **Never change a LOCKED CONTRACT value** (colors, fonts, instruments,
   multipliers, math conventions, dealer sign, 12 ENV keys, `schema_version` 1).
   See `docs/02-locked-contract.md`. If a task seems to require it, STOP and ask.
2. **The Snapshot contract has two mirrors that must stay byte-for-byte equal:**
   `services/engine/src/engine/schema.py` (pydantic) and
   `packages/contracts/src/snapshot.ts` (zod). Change one → change the other in
   the same commit, or the contract validators fail.
3. **Additive, non-breaking by default.** Add new functions/modules; do not
   rip out behaviour that already passes the T-01…T-10 gate. New Snapshot data
   follows the `ohlc` / `hiro` precedent: an **optional** field, no version bump.
4. **Engine `build_snapshot` is pure, deterministic, and calendar-free.** Keep
   it that way. Identical inputs must always produce an identical Snapshot. The
   caller supplies the resolved `session_state`; the engine owns no calendar.
5. **The five methodology divergences are decided** (see §5). Do not silently
   re-open them. The two heavy items (DDOI engine, proprietary metrics) are
   explicitly **not built** — do not build them without approval.
6. **Don't claim done with red tests.** Always run the verification suite (§4).

## 3. Repo map (where things live)

```
services/engine/   flowdesk-engine  — Python compute core (Black-76, IV, exposure,
                   field, levels, snapshot, hiro, surface, feed adapters, ingest)
services/api/      flowdesk-api     — FastAPI REST+WS, Discord OAuth, worker,
                   Redis/Timescale repos, session state machine
apps/web/          @flowdesk/web    — Next.js 14 frontend (heatmap, profiles, auth UI)
packages/contracts @flowdesk/contracts — zod mirror of Snapshot + /api/me
packages/tokens    @flowdesk/tokens — locked design tokens + Tailwind preset
infra/             docker-compose etc. (Fase 6 — currently only .gitkeep)
docs/              ALL human documentation (start at docs/README.md)
```

Two ecosystems are managed **separately**: TS/JS via pnpm workspaces
(`apps/*`, `packages/*`); Python via per-service `pyproject.toml` (NOT in the
pnpm workspace).

## 4. Verification — run after EVERY change

```bash
# Engine
cd services/engine && pytest && ruff check . && mypy
# API (engine must be installed editable first: pip install -e ../engine)
cd services/api && pytest && ruff check . && mypy
# TS
pnpm -r typecheck && pnpm -r lint
pnpm --filter @flowdesk/contracts validate   # zod contract: accepts example, rejects malformed
pnpm --filter @flowdesk/web test
# Engine golden fixture (after an INTENTIONAL contract change only)
cd services/engine && PYTHONPATH=src python tests/gen_golden.py
```

Known pre-existing baseline noise (NOT introduced by you, do not "fix" blindly):
engine `mypy -p engine` shows ~16 strict errors in locked core modules
(`snapshot.py`, `field.py`, `feed/__init__.py`); api `ruff` shows ~150 mostly
`UP`/`N818`/`B008`-false-positive findings. These predate current work and are
documented in `docs/08-status-and-gaps.md`. Scope any cleanup as its own task and
re-verify the golden + T-gate afterwards.

## 5. The five methodology divergences (DECIDED — do not re-open)

Full rationale + the heavy unbuilt items: `docs/reference/methodology-decisions.md`.

| # | Topic | Decision |
|---|---|---|
| 1 | GEX basis | **VOL** (`gamma·VOL·M·F²·0.01`), cumulative since RTH open. DDOI is a v3 parallel layer — **not built**, do not rip out VOL-GEX. |
| 2 | Call/Put walls | **Gamma-dollar** (`gamma·OI` per side), static, Top-3. |
| 3 | 0DTE day-count | **Real wall-clock** to 16:00 ET via `t_expiry_from_clock` (worker default). Fixed `0.5/365` only when `t_expiry` is pinned (tests). |
| 4 | HIRO data source | **`trades.side`** aggressor (B/A/N). No `tbbo` needed. |
| 5 | HIRO in Snapshot | **Optional** `hiro` field, **no** `schema_version` bump (follows `ohlc`). |

## 6. When you touch the Snapshot or data

- Edit `schema.py` AND `snapshot.ts` together; keep `CONTRACT.md` accurate.
- Regenerate FE session JSON after any engine change that affects snapshot values:
  ```bash
  cd services/engine && PYTHONPATH=src python scripts/gen_session_snapshots.py \
    --date 2026-06-09 --data-dir <ABS>/data/raw \
    --out ../../apps/web/public/sessions --quote-schema bbo-1m
  ```
- New optional Snapshot field → consumers must treat absence as valid.

## 7. House style

- Explanations may be in Indonesian; **code, identifiers, and docstrings in English**.
- Engine math modules are stdlib-only on the hot path where practical (Black-76,
  IV, exposure, levels, hiro, surface). `field.py` is the deliberate exception
  (numpy + scipy for the vectorized grid projection).
- Every module already carries a thorough docstring stating its locked formula
  and PRD references — match that bar when adding modules.
- Add a test for every behavioural change. Determinism is a feature: prefer
  closed-form/fixture tests over fuzzy thresholds.

## 8. The honest gap map (your backlog, in priority order)

See `docs/08-status-and-gaps.md` for the full version with file references. Short list:

1. **Validation/backtest harness** — the engine computes numbers nobody has
   proven correct against reality. There is **no** reconciliation of synthetic
   positioning vs. official ΔOI, and **no** check that GEX predicts /ES price.
   This is the single biggest source of "feels done but lacking."
2. **Live feed** — `LiveAdapter` is a stub; only historical-sim works.
3. **Frontend dashboard** — heatmap/profile primitives exist; the full TRACE
   dashboard matching `1.png` (incl. HIRO line render) is the largest remaining FE work.
4. **Surface / vanna / charm wiring** — `surface.py` + `black76.vanna/charm`
   exist but are isolated (not in Snapshot, no VEX/CHEX aggregation).
5. **DDOI engine & proprietary metrics** — deliberately unbuilt (needs approval).

Do NOT start a heavy item (1, 5) without confirming scope with the human first.
