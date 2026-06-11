# 00 — Overview

## What FlowDesk is

FlowDesk is a **0DTE dealer-positioning terminal** for index futures options. It
focuses on two instruments only — **/ES** (E-mini S&P 500) and **/NQ** (E-mini
Nasdaq-100) — and visualizes **gamma/delta exposure (GEX/DEX)**, key **levels**
(call/put walls, gamma flip, largest GEX/DEX), and an optional intraday
**HIRO**-style signed order-flow line.

The product answers one operator question, minute by minute: *where are dealers
likely forced to buy or sell, and how is that map shifting intraday?*

## Who it's for

A small, gated group of futures options traders. Access is controlled by a
**Discord role** (`DESK_ROLE_ID`) in a specific guild — there is no public signup,
no billing, no multi-tenant story. This keeps scope narrow on purpose.

## The big picture

```
Databento GLBX.MDP3 (definition, statistics, trades, mbp-1/bbo-1m)
        │  feed adapter (historical replay  |  live — stub)
        ▼
  flowdesk-engine (Python)
   Black-76 → IV → per-strike gamma/delta
   → exposure (GEX/DEX) → field (price×strike grid)
   → levels (walls/flip) → HIRO (optional)
        │  emits ONE canonical Snapshot per instrument per minute
        ▼
  flowdesk-api (FastAPI)
   worker drives the session state machine; REST + WebSocket;
   Discord OAuth gate; Redis (hot snapshot) + Timescale (history)
        │  Snapshot JSON (validated against the zod contract)
        ▼
  @flowdesk/web (Next.js)
   WebGL heatmap + exposure profiles + levels + auth UI
```

The **`Snapshot`** is the spine of the whole system. Every layer either produces
it, transports it, or renders it. Its schema is mirrored in Python (pydantic) and
TypeScript (zod) and must stay identical on both sides.

## Design philosophy

- **One canonical artifact.** No ad-hoc payloads; the Snapshot is the only thing
  that crosses the engine→api→web boundary.
- **Deterministic core.** `build_snapshot` is pure and calendar-free: same inputs
  → same output, guaranteed by a golden fixture.
- **Locked contract.** Visual identity, instruments, and math conventions are
  frozen so the product has a stable feel and reproducible numbers (see
  [`02-locked-contract.md`](02-locked-contract.md)).
- **Structural validation, not number matching.** GLBX /ES exposure will *not*
  equal a SPX-based vendor's numbers; correctness is judged on internal
  consistency and structural behaviour, not parity with SpotGamma.

## What this product is NOT (current scope)

- Not a live trading system — the live feed is a stub; today it replays history.
- Not a multi-asset platform — /ES and /NQ only.
- Not (yet) validated against reality — see [`08-status-and-gaps.md`](08-status-and-gaps.md).
