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
serves those snapshots over REST/WebSocket behind Discord-role auth. Everything
revolves around the `Snapshot` data contract (`schema_version` 2).

## 1. Read-before-you-work (in this order)

1. This file (`AGENTS.md`).
2. [`docs/02-locked-contract.md`](docs/02-locked-contract.md) — the LOCKED CONTRACT. Non-negotiable.
3. [`docs/01-architecture.md`](docs/01-architecture.md) — how the pieces fit.
4. [`docs/04-engine.md`](docs/04-engine.md) — the compute core (where most logic lives).
5. [`docs/08-status-and-gaps.md`](docs/08-status-and-gaps.md) — the **honest** map of what is real vs. stubbed vs. naive. **This is your task map.**
6. [`docs/10-acceptance-and-testing.md`](docs/10-acceptance-and-testing.md) — the T-01…T-10 gate. A regression here is a hard blocker.

## 2. Golden rules (do NOT violate without explicit human approval)

1. **Never change a LOCKED CONTRACT value** (colors, fonts, instruments,
   multipliers, math conventions, dealer sign, 12 ENV keys, `schema_version` 2).
   See `docs/02-locked-contract.md`. If a task seems to require it, STOP and ask.
2. **The Snapshot contract has two mirrors that must stay byte-for-byte equal:**
   `services/engine/src/engine/schema.py` (pydantic) and
   `packages/contracts/src/snapshot.ts` (zod). Change one → change the other in
   the same commit, or the contract validators fail.
3. **Additive, non-breaking by default.** Add new functions/modules; do not
   rip out behaviour that already passes the T-01…T-10 gate. New Snapshot data
   follows the `ohlc` / `flux` precedent: an **optional** field, no version bump.
4. **Engine `build_snapshot` is pure, deterministic, and calendar-free.** Keep
   it that way. Identical inputs must always produce an identical Snapshot. The
   caller supplies the resolved `session_state`; the engine owns no calendar.
5. **The five methodology divergences are decided** (see §5). Do not silently
   re-open them. The two heavy items (DDOI engine, proprietary metrics) **are
   built** as EXPERIMENTAL, alongside (not replacing) VOL-GEX — do not let
   them drive primary signals without explicit human approval and a passing
   validation report.
6. **Don't claim done with red tests.** Always run the verification suite (§4).
7. **Assert data tenor/provenance before any offline analysis number.** Every
   `analysis/`-harness computation MUST call `assert_0dte` / `assert_session_iids_0dte`
   (from `analysis.harness.provenance`) at the data-load chokepoint, BEFORE
   computing any metric or snapshot. A number produced without a stamped
   `DataProvenance` is INVALID and must not be reported. This guards against the
   documented quarterly-as-0DTE contamination (the DDOI "49.2/50.8" artefact, which
   slipped through because no tenor assertion existed at load). RESIDUAL: only
   `run_validation.py` is wired through the guard today; routing the other duplicated
   loaders (`lapis1`, `rerun_zerodte`, `synthetic_oi_v2/v3/v4`, `ddoi` via `lapis1`)
   is an open TODO in `provenance.py`.

## 3. Repo map (where things live)

```
services/engine/   flowdesk-engine  — Python compute core (Black-76, IV, exposure,
                   field, levels, snapshot, flux, surface, feed adapters, ingest)
services/api/      flowdesk-api     — FastAPI REST+WS, Discord OAuth, worker,
                   Redis/Timescale repos, session state machine
packages/contracts @flowdesk/contracts — zod mirror of Snapshot + /api/me (the
                   ONLY real package in pnpm workspace)
packages/tokens/   EMPTY — leftover after the 2026-06-15 FE deletion. Do NOT
                   resurrect; locked tokens live in docs/02-locked-contract.md.
apps/dashboard/    @flowdesk/dashboard — Next.js 15 + lightweight-charts (port 4325).
                   In-progress rebuild. STANDALONE: own node_modules + pnpm-lock,
                   NOT in pnpm-workspace.yaml.
apps/landing/      @flowdesk/landing — Next.js marketing site (port 4321, distinct
                   from the dashboard's 4325 so both can run). STANDALONE: own
                   node_modules + package-lock.json, NOT in pnpm-workspace.yaml.
analysis/          Offline research/eval harnesses. `analysis/harness/provenance.py`
                   is the chokepoint that enforces 0DTE tenor (rule 2.7).
infra/             docker-compose.yml (DEV Redis + TimescaleDB stack) + .gitkeep.
                   Prod compose / Caddy / bootstrap land per the ops runbook.
docs/              ALL human documentation (start at docs/README.md).
```

Three ecosystems are managed **separately**:
- pnpm workspace: `packages/*` only (currently just `@flowdesk/contracts`).
- `apps/dashboard` and `apps/landing`: each has its own `node_modules` and lockfile.
  Run `pnpm install` *inside* the app dir before `pnpm dev` / `pnpm build`. The
  root `pnpm install` will NOT install them. The README mention of `pnpm dev:web`
  is stale — no such script exists.
- Python: per-service `pyproject.toml` under `services/engine` and `services/api`.

## 4. Verification — run after EVERY change

CI exists (`.github/workflows/ci.yml`): pytest is a HARD gate for engine + api,
ruff/mypy are advisory (`continue-on-error`), and contracts run typecheck + zod
validate. There is no pre-commit hook. Always run the checks below locally too —
CI mirrors them but you should not rely on it as your only gate.

```bash
# Engine — both linters are strict and gated by mypy strict mode.
cd services/engine && pytest && ruff check . && mypy
# API — engine MUST be installed editable first or imports break.
cd services/api && pip install -e ../engine && pytest && ruff check . && mypy
# TS contracts (only thing in the pnpm workspace).
pnpm -r typecheck && pnpm -r lint
pnpm --filter @flowdesk/contracts validate   # zod contract: accepts example, rejects malformed
# Engine golden fixture (after an INTENTIONAL contract change only).
cd services/engine && PYTHONPATH=src python tests/gen_golden.py
```

`Makefile` shortcuts exist: `make dev-api`, `make lint`, `make typecheck`
(the latter two run BOTH pnpm and per-service ruff/mypy in one go).

The Databento ingest script needs an extra: `pip install -e ".[dev,ingest]"`
in `services/engine`. The base `[dev]` install is enough for the engine, the
historical adapter, and all tests — do not pull `ingest` unless you actually
hit the live API.

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
| 4 | FLUX data source | **`trades.side`** aggressor (B/A/N). No `tbbo` needed. |
| 5 | FLUX in Snapshot | **Optional** `flux` field, **no** `schema_version` bump (follows `ohlc`). |

## 6. When you touch the Snapshot or data

- Edit `schema.py` AND `snapshot.ts` together; keep `CONTRACT.md` accurate.
- Regenerate session-snapshot JSON after any engine change that affects snapshot values:
  ```bash
  cd services/engine && PYTHONPATH=src python scripts/gen_session_snapshots.py \
    --date 2026-06-09 --data-dir <ABS>/data/raw \
    --out <output-dir> --quote-schema bbo-1m
  ```
- New optional Snapshot field → consumers must treat absence as valid.

## 7. House style

- Explanations may be in Indonesian; **code, identifiers, and docstrings in English**.
- Engine math modules are stdlib-only on the hot path where practical (Black-76,
  IV, exposure, levels, flux, surface). `field.py` is the deliberate exception
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
2. **Live feed** — `LiveAdapter` built with two-key arming + circuit breaker
   (Phase 3, 2026-06-15). Beta image keeps `LIVE_FEED_ARMED=1` absent so it
   stays disarmed; flipping it requires the operator runbook procedure.
3. **Frontend** — the prior `apps/web` Next.js app and `@flowdesk/tokens`
   package were deleted on 2026-06-15 and the rebuild is **in progress** at
   `apps/dashboard/` (Next.js 15 + lightweight-charts, port 4325). Fog lens is
   a **two-zone** terminal (2026-06-18 redesign): LEFT = scrolling strike
   ladder + per-strike `net_gex` bars ($5) + session range hairline + dotted
   IV-smile overlay (EXPERIMENTAL); RIGHT = `lightweight-charts` price candles
   with selectable key-level lines + ratio overlays (GEX+ share / ATM IV /
   skew) + a session-metrics strip. Pure helpers (`strikeMath.ts`,
   `levelsChart.ts`) are unit-tested with `node:test`. Flux & Arc remain
   placeholders; API wiring (`@flowdesk/contracts` → `/api/snapshot` + `/ws`)
   is the next planned step. See `docs/09-roadmap.md` §B and the
   2026-06-18 checkpoint in `docs/PROGRESS.md`.
4. **Surface / vanna / charm wiring** — `surface.py` (SVI / expected move)
   wired into the optional Snapshot fields and VEX/CHEX aggregated from
   `black76.vanna/charm` (commits `691a894`, `7eeac8b` series). Labelled
   EXPERIMENTAL — must not drive a regime classifier without caveat.
5. **DDOI engine & proprietary metrics** — built EXPERIMENTAL alongside (not
   replacing) VOL-GEX (commits `f4d614c`, `6be20ff`). Both are
   `NOT-VALIDATED` because the 90-day forward run was dropped; they ship
   with the EXPERIMENTAL label and must NOT drive primary signals.
