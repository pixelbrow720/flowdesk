# FlowDesk — Fase 4.3: Profile line + shared price axis

The locked dashboard chart layout (PRD #4): a single full-width row split into
LEFT profile line (~22%), the CENTERED shared strike axis (~72px), and the RIGHT
heatmap (4.2). All three share ONE Y-scale so the profile rows, axis ticks, and
heatmap rows align exactly. Renders from the mock snapshot — no backend.

## Prerequisites & run

- Node `>=20 <21` (machine Node 24), pnpm `9.7.0` via corepack. No new deps.

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/dashboard   profile | shared axis | heatmap (GEX/DEX + instrument + theme)
```

## Manual verification checklist

- [x] `typecheck` — clean (strict + noUncheckedIndexedAccess).
- [x] `lint` — no ESLint warnings/errors.
- [x] `build` — compiles; `/preview/dashboard` prerenders.
- [x] **Browser layout measured (Playwright)**: profile width = **0.22** of the
      row (locked ~22%), axis column = **72px** (locked), profile/axis/canvas
      share the same top (63/63/64px) and height (730/728px) → rows aligned
      within 1–2px. Zero console errors (only `/favicon.ico` 404).
- [x] Screenshot confirms: ONE signed profile line (turquoise positive / crimson
      negative) across a centered zero baseline, NO numbers on the line, NO
      gradient fill; a single shared strike axis with the dashed current-price
      line + one price tag; heatmap fills the remaining width.
- [x] GEX/DEX toggle swaps the profile series (wired to the store).

## File list (added in this task)

```
apps/web/
  lib/scale.ts                         # shared linear Y-scale (strike <-> y), higher strike at top
  components/chart/
    profile-line.tsx                   # single signed SVG line, color by sign, zero baseline
    shared-axis.tsx                    # strike ticks (5 ES / 10 NQ) + dashed price line + 1 tag
    chart-layout.tsx                   # composes profile ~22% | axis 72px | heatmap on one scale
    index.ts                           # barrel
  app/preview/dashboard/page.tsx       # standalone layout preview
```

## How alignment works

`lib/scale.ts` builds a single linear `YScale` from the snapshot axis
(`strike_min`/`strike_max`/`step`) and the measured pixel height. The convention
matches the 4.2 heatmap (Y flipped so higher strike is at the top), so:

- `ProfileLine` maps each `profile[].strike` -> `scale.yOf(strike)` for its Y,
  and the signed value -> X around a centered zero baseline.
- `SharedAxis` renders tick labels at `scale.yOf(tick)` and the price line at
  `scale.yOf(forward)`.
- `Heatmap` (4.2) already flips its texture rows over the same strike domain.

`ChartLayout` measures its own size via `ResizeObserver`, builds the scale once,
and feeds the same `scale` + `height` to all three columns — so there is exactly
ONE source of truth for vertical position.

## Assumptions

- **Profile X-normalization** uses the max abs of the visible metric so the line
  always spans the panel symmetrically around the centered zero baseline; the
  line carries NO numeric labels (per the locked layout).
- **Tick label thinning**: labels are drawn every `step` but skipped to keep a
  ~16px minimum gap so they never collide at small heights; the dashed line is
  always at the exact forward price with a single tag.
- **Profile fraction 0.22 / axis 72px** are the locked defaults, exposed as props
  on `ChartLayout` for the full app shell to override if needed.
- The heatmap still synthesizes its 2D field for offline dev (see README.4.2);
  the profile reads the real 1D `snapshot.profile`.
- No `TODO-FROM-OWNER` items for this task.
```
