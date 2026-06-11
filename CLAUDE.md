# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FlowDesk — a real-time 0DTE GEX/DEX options terminal for /ES & /NQ futures. A Python compute engine prices the option chain and emits one canonical **Snapshot** per instrument per minute; a FastAPI service serves those snapshots over REST/WS behind Discord auth; a Next.js app renders the heatmap + exposure profiles.

## Monorepo layout

Two ecosystems live side by side and are managed **separately**:

- **TS/JS** via pnpm workspaces (`pnpm-workspace.yaml` → `apps/*`, `packages/*`):
  - `apps/web` (`@flowdesk/web`) — Next.js 14 frontend.
  - `packages/contracts` (`@flowdesk/contracts`) — zod mirror of the Snapshot + `/api/me` contracts.
  - `packages/tokens` (`@flowdesk/tokens`) — locked design tokens + Tailwind preset.
- **Python** via per-service `pyproject.toml` (NOT in the pnpm workspace):
  - `services/engine` (`flowdesk-engine`) — pricing/analytics: Black-76, IV solve, exposure, field, levels, snapshot builder, feed adapters.
  - `services/api` (`flowdesk-api`) — FastAPI REST + WebSocket, Discord OAuth2, Redis/Timescale reads, per-minute worker.

`STITCHING_GUIDE.md` documents how release patches (0.1 → 1.6 → Fase 4/5/6) overlay into this tree. Read it before structural work — it also holds the locked contract (below) and the PRD acceptance gate (T-01…T-10).

## Commands

Root (TS workspaces):
```bash
pnpm dev:web          # next dev on :3000
pnpm build:web
pnpm lint             # pnpm -r lint across TS packages
pnpm typecheck        # pnpm -r typecheck (tsc --noEmit)
pnpm --filter @flowdesk/contracts validate   # run the zod contract validator (tsx)
pnpm --filter @flowdesk/web test             # vitest run (frontend unit tests)
```

`make lint` / `make typecheck` run the TS commands AND the Python ones (ruff + mypy in both services). `make dev-api` runs uvicorn.

Engine (`cd services/engine`):
```bash
python -m venv .venv && source .venv/bin/activate   # Python >=3.11,<3.13
pip install -e ".[dev]"
pytest                                  # full suite (testpaths=tests, pythonpath=src+tests)
pytest tests/test_snapshot.py -q        # single file
pytest tests/test_snapshot.py::test_name # single test
ruff check . && mypy                    # mypy is strict=true
PYTHONPATH=src python tests/gen_golden.py   # regenerate golden snapshot fixture
```

API (`cd services/api`):
```bash
pip install -e .          # depends on flowdesk-engine (pip install -e ../engine first)
pip install -e ".[dev]"
pytest                    # pythonpath=["src","."] — `db` is top-level alongside `src`
uvicorn api.main:app --reload --port 8000 --app-dir src
ruff check . && mypy
```

## Architecture: the Snapshot pipeline

Everything revolves around **one data structure, the Snapshot (`schema_version` 1)**. It is defined canonically in `services/engine/src/engine/schema.py` (pydantic) and mirrored in `packages/contracts/src/snapshot.ts` (zod). **These two MUST stay byte-for-byte equivalent** — a change to one requires the matching change to the other, or the contract validators fail.

Compute flow (`engine/snapshot.py::build_snapshot`, pure & deterministic, calendar-free):
```
raw chain quotes
  -> IV solve            (iv.implied_vol / is_iv_reliable)
  -> greeks              (black76.delta / gamma)
  -> per-strike exposure (exposure.build_profile / net_gamma)   [from VOL]
  -> heatmap field       (field.build_field)
  -> key levels          (levels.compute_levels)   [walls by gamma-$ (gamma·OI), dynamic levels from VOL]
  -> regime + session stamping
  -> validated Snapshot  (schema.parse_snapshot)
```
The builder owns no calendar logic — the caller passes a resolved `session_state`; the only time math is UTC→America/New_York to derive `minute_index` (0 at the 09:30 ET open) and `session_date`.

Runtime data flow (`services/api`):
```
FeedAdapter (historical | live, selected by FEED_MODE; identical OptionChainMinute shape — AC-A3)
  -> MinuteWorker.tick()  (api/worker.py — one cycle per ET minute, fully injectable for tests)
       LIVE  -> build_snapshot -> SnapshotRepository.save (Timescale) + StateStore.set_now (Redis -> WS push)
       STALE -> re-publish last frame with stale=true (does NOT advance ts)
       CLOSED/HOLIDAY/PREMARKET -> idle
  -> REST/WS (api/main.py, api/ws.py) -> frontend
```
Backends are dependency-injected via `get_state_store` / `get_repo` (overridden with fakes in tests; real Redis/Timescale wired in the app lifespan from env). `api/session.py` owns the PRD #9 session state machine.

Auth (`api/auth*.py`, `api/security.py`, `api/entitlement.py`): Discord OAuth2 (`identify guilds.members.read`), signed session cookie, daily re-check. Data endpoints (snapshot, replay, `/ws`) are DESK-gated → 401 unauthenticated / 403 no-DESK. **`/api/me` is intentionally PUBLIC** and projects the session into `ANON | NO_DESK | DESK` so the FE renders the denied/blur experience without a 401. FE must not rely on the 403 body — the not-member vs no-desk distinction comes only from `/api/me`. See `api/FE_AUTH_CONTRACT.md`.

## LOCKED CONTRACT — do not change without explicit instruction

These values are fixed across the whole stack (full text in `STITCHING_GUIDE.md` §2):
- **Colors:** turquoise `#40E0D0` (positive/support), crimson `#E0183C` (negative/resistance), base `#000000`. Heatmap interpolated in OKLab/LCH.
- **Fonts:** Space Grotesk (UI) + JetBrains Mono (numbers). **Never Inter.**
- **Instruments:** /ES multiplier $50/pt, step 5; /NQ $20/pt, step 10. Only ES & NQ.
- **Session:** RTH 09:30–16:00 America/New_York, 1-minute cadence, 90-day rolling replay.
- **Math:** Black-76; `r = ln(1 + SOFR)`; IV from mid via Newton-Raphson → bisection, tol 1e-6.
- **Dealer convention:** long calls / short puts. `GEX_strike = gamma * VOL * M * F² * 0.01`; VOL cumulative since RTH open. Net GEX > 0 → pinning (turquoise), < 0 → volatile (crimson).
- **Levels:** Call/Put Wall by **gamma-dollar** (`gamma · OI` per side), static, Top 3 (Divergence #2 → option B; supersedes the original raw-OI rule); Gamma Flip + Largest GEX/DEX by **VOL**, dynamic (≤ 1–2 strike tolerance).
- **0DTE day-count:** real wall-clock year-fraction to the 16:00 ET settlement via `t_expiry_from_clock` (Divergence #3 → option A; the worker computes it per minute, the legacy fixed `0.5/365` is used only when an explicit `t_expiry` is pinned, e.g. in tests).
- **HIRO:** cumulative dealer delta-notional hedging flow since the RTH open (`engine.hiro`), exposed as the **optional** `hiro` Snapshot field (Divergence #5 → option A; additive like `ohlc`, **no** `schema_version` bump). The intraday line is reconstructed FE-side from the per-minute frame sequence.
- **Auth:** Discord OAuth2 scopes `identify guilds.members.read`. Snapshot `schema_version` 1.
- **ENV:** exactly 12 locked keys (`DISCORD_CLIENT_ID/SECRET/GUILD_ID/DESK_ROLE_ID`, `SESSION_SECRET`, `CORS_ORIGINS`, `FEED_MODE`, `DATABENTO_API_KEY`, `DATA_DIR`, `TIMESCALE_DSN`, `REDIS_URL`, `SOFR_RATE`). **Do not add a 13th required key.** Optional dev toggles (non-locked): `PUBLIC_BASE_URL`, `COOKIE_INSECURE`, `DISCORD_JOIN_URL`.

## Conventions & gotchas

- Engine `mypy` and API `mypy` both run `strict = true` — no untyped escapes.
- Flipping `FEED_MODE` (historical ↔ live) MUST require zero code changes downstream (AC-A3); both feed adapters emit the identical `OptionChainMinute`.
- The README's "1.3" / version numbers refer to PRD pipeline-step IDs, not release numbers; releases are the sequential `0.1 … 0.9 → 1.0 … 1.6` scheme.
- `tzdata` is pinned so `zoneinfo` resolves `America/New_York` on minimal containers.
- Dev without Discord: `MOCK_ACCESS_STATE=NO_DESK python services/api/mocks/mock_me_server.py 8787`, then point the FE at it.
- The PRD acceptance gate (T-01…T-10 in `STITCHING_GUIDE.md` §7) is the bar for engine/state changes; a regression there is a hard blocker.
