# FlowDesk — Fase 4.5: Floating glass toolbar (auto-fade) + toggles

The floating glass toolbar overlaying the chart (PRD #4): glassmorphism-lite,
auto-fades after 2.5s idle and reappears on pointer movement over the chart,
holding visible while hovered/focused. Hosts the chart toggles — Net GEX/DEX,
Gamma/Delta, smooth/block, theme, and the Wall Top 1/2/3 key-levels picker — all
wired to the store, keyboard accessible, respecting prefers-reduced-motion.

## Prerequisites & run

- Node `>=20 <21` (machine Node 24), pnpm `9.7.0` via corepack. No new deps.

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/dashboard   floating toolbar over the chart (move mouse / wait 2.5s)
```

## Manual verification checklist

- [x] `typecheck` — clean (strict + noUncheckedIndexedAccess).
- [x] `lint` — no ESLint warnings/errors.
- [x] `build` — compiles; `/preview/dashboard` prerenders.
- [x] **Auto-fade measured (Playwright)**: opacity `1` on load → `0` after 2.5s
      idle (`fades: true`) → back to `1` on pointer move (`reappears: true`).
- [x] **Wall picker works**: clicking TOP 3 sets the store (`wallCount = 3`,
      aria-checked reflects "TOP 3").
- [x] All toggles wired to the store (GEX/DEX, Gamma/Delta, smooth/block, theme).
- [x] Keyboard accessible: focusing any control holds the bar visible
      (focus-capture) and releases on blur out.
- [x] Zero console errors (only `/favicon.ico` 404).

## File list (added/changed)

```
apps/web/
  lib/store.ts                              # + wallCount (1|2|3, default 1) + setWallCount
  lib/use-auto-fade.ts                      # 2.5s idle fade / pointer-wake / hold / reduced-motion
  components/toolbar/
    floating-toolbar.tsx                    # glass toolbar with all chart toggles
    index.ts                                # barrel
  app/preview/dashboard/page.tsx            # toolbar overlays the chart (relative container)
```

## How auto-fade works

`useAutoFade({ idleMs: 2500, hold })`:
- starts visible; arms a 2.5s timer that sets `visible=false` when it fires.
- `onPointerMove` (attached to the toolbar's positioned ancestor — the chart
  container) shows it and re-arms the timer.
- `hold` (true while the pointer is over the bar or focus is within) cancels the
  timer and pins it visible; releasing re-arms.
- under `prefers-reduced-motion: reduce` the bar never fades (always visible),
  and the global reduced-motion CSS rule neutralizes the opacity transition.

The toolbar uses `pointer-events-none` on its wrapper but `pointer-events-auto`
on the glass panel, so the faded bar never blocks chart interaction and the
ancestor still receives the pointermove that wakes it.

## Assumptions

- **Wall Top 1/2/3** is stored as `wallCount` now; the actual wall overlay
  rendering on the heatmap/axis lands with the key-levels overlay task. Default
  is **Top 1** per PRD #5.
- The toolbar is positioned bottom-center over the chart; it must be mounted
  inside a `position: relative` container (the preview wraps the chart in one).
- The dev-only connection-state switch + regime bar remain in the preview strip;
  in the full app shell the toolbar owns the chart toggles and the strip goes
  away.
- No `TODO-FROM-OWNER` items for this task.
```
