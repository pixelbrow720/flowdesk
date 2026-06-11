# 01 — Architecture

## Monorepo layout

```
flowdesk-main/
├─ apps/web/             @flowdesk/web      Next.js 14 frontend
├─ packages/
│  ├─ contracts/         @flowdesk/contracts  zod mirror of Snapshot + /api/me
│  └─ tokens/            @flowdesk/tokens     locked design tokens + Tailwind preset
├─ services/
│  ├─ engine/            flowdesk-engine    Python compute core
│  └─ api/               flowdesk-api       FastAPI REST + WS + worker
├─ infra/                (Fase 6 — only .gitkeep today)
└─ docs/                 all documentation
```

**Two toolchains, deliberately separate:**

- **TypeScript** via pnpm workspaces — `apps/*` and `packages/*` only.
- **Python** via per-service `pyproject.toml` — `services/engine` and
  `services/api` are **not** in the pnpm workspace. `flowdesk-api` depends on
  `flowdesk-engine` and expects it installed editable (`pip install -e ../engine`).

## The four packages

### `flowdesk-engine` (services/engine)
The brain. Pure-Python compute. Given a chain of option quotes/trades plus a
forward price and rate, it produces a `Snapshot`. Stdlib-only on the hot math
path except `field.py` (numpy + scipy). Owns the feed adapters and the Databento
ingest script. See [`04-engine.md`](04-engine.md) and [`05-data-and-feeds.md`](05-data-and-feeds.md).

### `flowdesk-api` (services/api)
The transport + control plane. A **worker** advances each instrument's session
state machine (PREMARKET → LIVE → CLOSED, etc.), calls the engine each minute,
writes the hot snapshot to **Redis** and history to **Timescale**, and pushes to
clients over **WebSocket**. REST serves the latest/historical snapshots and
`/api/me`. All gated by **Discord OAuth + role**. See [`06-api-and-auth.md`](06-api-and-auth.md).

### `@flowdesk/contracts` (packages/contracts)
The zod mirror of the Snapshot and the `/api/me` payload. This is the
TypeScript half of the cross-language data contract; it must match the engine's
pydantic models byte-for-byte. `CONTRACT.md` lives here.

### `@flowdesk/tokens` (packages/tokens)
The locked design tokens (colors, fonts, spacing) exported as TS + a Tailwind
preset, so the visual contract is enforced in code, not by convention.

## Runtime data flow (one minute)

1. The **worker** ticks for instrument *I* at minute *m*.
2. It pulls the current chain from the **feed adapter** (historical replay today).
3. It resolves the **session state** and **time-to-expiry** (real wall-clock to
   16:00 ET) and calls `engine.build_snapshot(...)`.
4. The engine prices the chain (Black-76 → IV → greeks), aggregates exposure,
   projects the field grid, extracts levels, optionally computes HIRO, and
   returns a `Snapshot`.
5. The API validates, stores it (Redis hot, Timescale history), and broadcasts
   it over WebSocket to subscribed clients.
6. The **web app** receives the Snapshot, re-validates it against the zod
   contract, and renders the heatmap + profiles + levels.

## The contract spine

The single most important invariant in the codebase:

> `services/engine/src/engine/schema.py` (pydantic) **==**
> `packages/contracts/src/snapshot.ts` (zod)

If these diverge, the FE rejects valid snapshots or accepts malformed ones.
Any change to one is a change to both, in the same commit, plus a golden-fixture
regen. See [`03-data-contract.md`](03-data-contract.md).

## Session state machine

Each instrument moves through `PREMARKET | LIVE | STALE | CLOSED | HOLIDAY`.
The state is resolved **outside** the engine and passed in, preserving the
engine's calendar-free purity. `stale` and `expired` flags ride along on the
Snapshot so the FE can dim/freeze the display appropriately.
