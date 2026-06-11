# FlowDesk — Fase 4.4: Topbar + segmented ES|NQ + regime bar

The thin 44px topbar (PRD #4.2) — FlowDesk wordmark, the ES|NQ instrument
switch, ET clock, connection-state dot, and a settings gear — plus the regime
indicator: a BAR/PILL (explicitly NOT a speedometer/gauge) that goes
turquoise↔crimson by net-gamma sign with a stability % in JetBrains Mono.

## Prerequisites & run

- Node `>=20 <21` (machine Node 24), pnpm `9.7.0` via corepack. No new deps.

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/dashboard   topbar + regime bar over the 4.3 chart layout
```

## Manual verification checklist

- [x] `typecheck` — clean (strict + noUncheckedIndexedAccess).
- [x] `lint` — no ESLint warnings/errors.
- [x] `build` — compiles; `/preview/dashboard` prerenders.
- [x] **Browser (Playwright)**: topbar height measured at exactly **44px**.
- [x] **Regime is a bar, not a gauge**: the regime element contains no
      `canvas`/`svg` arc (`regimeIsBar: true`) — a horizontal fill + mono %.
- [x] ES|NQ switch updates the store and flips the regime by sign:
      ES → "PINNING, stability 63.5%" (turquoise), NQ → "VOLATILE, stability
      38.0%" (crimson).
- [x] ET clock derives from `snapshot.ts` (13:31Z → **09:31:00 ET**, EDT).
- [x] Connection dot reflects LIVE/STALE/REPLAY from the store (LIVE pulses
      turquoise, STALE crimson, REPLAY neutral).
- [x] Zero console errors (only `/favicon.ico` 404).

## File list (added in this task)

```
apps/web/
  components/topbar/
    topbar.tsx          # 44px topbar: wordmark + ES|NQ + ET clock + dot + gear
    regime-bar.tsx      # PINNING/VOLATILE pill, horizontal stability bar, mono %
    connection-dot.tsx  # LIVE/STALE/REPLAY/CONNECTING/OFFLINE status dot + label
    et-clock.tsx        # HH:MM:SS ET derived from snapshot.ts (America/New_York)
    index.ts            # barrel
  app/preview/dashboard/page.tsx   # now uses the real Topbar + RegimeBar
```

## Notes

- **Topbar height is locked to 44px** via `h-[44px]` (an explicit arbitrary
  value, since the token spacing scale tops out at 64 and has no 44 step). All
  other spacing/color comes from tokens.
- **Regime sign drives everything**: `snapshot.regime.sign > 0` → PINNING
  (turquoise), `< 0` → VOLATILE (crimson), `0` → NEUTRAL. The stability % is the
  bar fill width and the mono readout. No gauge/needle anywhere (anti-AI-look).
- **ET clock is data-tied** (PRD #4.3: clock ← `ts`), not wall-clock — so it
  stays deterministic and matches the rendered snapshot frame. In LIVE the
  realtime layer (4.7) advances `ts` each minute.
- The settings gear calls an optional `onOpenSettings` prop — wired to the
  slide-in panel in 4.8.
- The connection-state switcher in the preview is a dev control to exercise the
  dot; the real connection state will come from the WS client (4.7).

## Assumptions

- ConnectionDot covers all five `ConnectionState` values from the store
  (LIVE/STALE/REPLAY/CONNECTING/OFFLINE); only LIVE/STALE/REPLAY are in the
  locked PRD list, the other two are transitional states for the WS layer.
- No `TODO-FROM-OWNER` items for this task.
```
