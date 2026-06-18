# Handoff — FlowDesk FOG Page (Heatmap TRACE-Style)

> **Last updated: 2026-06-19**. WebGL TRACE-grade heatmap rewrite is DONE
> (2026-06-17). A mini-session on 2026-06-19 fixed three Fog bugs, added an
> additive IV-smile call/put split (new `iv_smile` Snapshot field), and
> reworked the layout into ONE scrolling page with shared chrome. See
> **`HANDOFF-MINI-SESSION.md`** for the full 2026-06-19 handoff. This file
> (main HANDOFF) covers the WebGL heatmap only.

## Server Status
- **Dashboard**: `apps/dashboard` port **4325**
- **Dev command** (cmd.exe): `cd apps\dashboard && node node_modules\next\dist\bin\next dev -p 4325`
- **Data**: `apps/dashboard/public/data/ES_2026-06-09.json` (390 frames) + `NQ_2026-06-09.json`.
  `public/data/` is now **gitignored** (regenerable, ~18MB).
- **URL**: `http://localhost:4325/fog`

## Verify commands (dashboard)
- `cd apps\dashboard && npm run typecheck`  → must exit 0
- `cd apps\dashboard && npm run build`       → real gate, must compile
- `npm run lint` is NOT usable — ESLint unconfigured, drops into an interactive
  prompt that cannot be answered headless. Do not rely on it.
- pnpm is not on PATH; use `corepack pnpm ...` for installs (how `regl` was added).

## Engine Backend (OK — DO NOT change)
- Pipeline: DBN raw → CSV cache (`data/cache/`, gitignored) → snapshot JSON via
  `services/engine/scripts/gen_session_snapshots.py`.
- FOG field: `services/engine/src/engine/fog.py` — TRACE-style Black-76 field
  projection per hypothetical price, aggregated. Conceptually correct.
- Heatmap **uses REAL data** (verified): a mid-session frame has 87 non-zero
  gamma values, range ~ -3.3e9 … +4.5e9. Not synthetic.

## DONE this session (all passes typecheck + build; NOTHING committed)
Files: `apps/dashboard/src/components/fog/GexHeatmap.tsx` (Canvas2D, ~615 lines)
and `apps/dashboard/src/app/fog/page.tsx`.

1. **Locked colors → DEEP palette** (human-approved contract change): turquoise
   `#0FB5A8`, crimson `#B5002E` (was bright `#40E0D0` / `#E0183C`). Synced across
   code + `docs/02-locked-contract.md`, `09-roadmap.md`,
   `reference/Stitching-Guide.md`, `reference/PRD-Gabungan.md`,
   `reference/Build-Playbook-PerFase.md`, `research/verified/README.md`, this file.
   `docs/research/archive/*` intentionally left as historical record.
2. **Price line → candlesticks**, 5-min buckets (~78 candles). 0DTE snapshots have
   `ohlc == null`, so OHLC is built from the per-minute `forward` series:
   open=first, high=max, low=min, close=last per bucket. Up→body `#FAFAF7`,
   down→body `#000000`, wick+border `#FAFAF7`.
3. **Y-axis orientation bug FIXED**: `buildSharedAxis` now returns levels
   DESCENDING (high price on top), matching right-axis labels + left ladder.
   Map: `y = marginTop + ((axisMax - price)/(axisMax-axisMin))*plotH`.
4. **Price axis labels moved RIGHT** (marginLeft 12, marginRight 58).
5. **Crosshair** on a separate overlay canvas (`crosshairRef`) so pointer moves
   don't re-render the heavy heatmap. Dashed cross + price box (right) + time box
   (bottom). Layout shared via `layoutRef`.

## DONE 2026-06-17: WebGL TRACE-grade heatmap (committed)
Right panel now = SpotGamma TRACE look — smooth, cloud/smoke-like, no vertical
banding. Built with **regl 2.1.1**, verified via `next build` + Playwright shot.

New file `apps/dashboard/src/components/fog/glHeatmap.ts` (regl renderer):
- Field packed into an **RGBA8** texture (R high byte / G low byte = 16-bit
  signed value) sampled NEAREST, with hand-rolled bilinear decode in the shader.
  This avoids OES_texture_float entirely → plain WebGL1, runs under SwiftShader.
- Diverging colormap deep turquoise `#0FB5A8` → black → crimson `#B5002E`,
  power 0.7. Bloom = bright-pass → separable gaussian blur (half-res FBO) →
  additive composite ("senter" glow).
- `createGLHeatmap(canvas) → { render(field, plot, dpr, opts?), destroy() }`.

`GexHeatmap.tsx` rewired:
- `buildSharedAxis` → clamp to **median forward ±180pt** snapped to tick (the
  `PRICE_BAND_PT` const), NOT union range.
- `resampleFrame` → **edge-hold** (clamp to nearest edge value) instead of NaN
  outside a frame's `price_grid`. This kills the banding (root cause below).
- Removed the Canvas2D `colorForValue` + offscreen-bitmap path; WebGL paints the
  field now. The Canvas2D layer is transparent and carries only the overlays.
- Canvas stack (DOM order): `glCanvasRef` (WebGL field, bottom) → `canvasRef`
  (contour/candles/gamma-line/axis, pointer-events-none) → `crosshairRef` (top).

### Root cause of banding (VERIFIED — do not re-investigate)
`fog.price_grid` SHIFTS frame-to-frame: 45 distinct grid-mins (7040…7235), 46
distinct grid-maxs (7610…7710), length varies 87–90. Union axis spans 7040–7710
(~134 levels) but each frame covers only ~87–90, so every minute has large NaN
regions top/bottom; the moving coverage edge draws the hard vertical streaks.
Fixed by clamp to a tight band around forward + edge-extrapolate (above).

### Tuning knobs if look needs adjusting
- Smoothing: `sigmaTime` / `sigmaPrice` in `GexHeatmap.tsx` render effect.
- Bloom: `RenderOptions` in `glHeatmap.ts` (`power`, `bloomThreshold`,
  `bloomIntensity`, `bloomRadius`) — currently defaults.
- Band width: `PRICE_BAND_PT` (180) at top of `GexHeatmap.tsx`.
- Contour levels [0.2,0.4,0.6,0.8] at ~0.25 alpha bone-white (Canvas2D overlay).

### Reference docs
- `docs/reference/reverse-engineering-trace-gamma-heatmap.md` — full recipe:
  field → smoothing (inter-strike interp + 2D gaussian blur) → diverging colormap
  → contour → bloom. Has Canvas2D "fast path" and WebGL "production path" + libs.
- `docs/research/spotgamma-trace.md` — UX/visual direction only (no render math).

## Visual verification loop (Playwright IS available — use it)
playwright-core is at `C:/Users/ollama/AppData/Roaming/npm/node_modules/playwright-core`,
Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`. Pattern: write a
small Node script that launches chromium with that executablePath,
`goto('http://localhost:4325/fog')`, optionally `page.mouse.move(...)` to trigger
the crosshair, `screenshot` to a temp PNG, then Read the PNG to inspect. This is
how candles/crosshair were verified.

## Locked Brand Colors (source of truth: docs/02-locked-contract.md)
- Turquoise (positive / call / long-gamma): `#0FB5A8`
- Crimson (negative / put / short-gamma): `#B5002E`
- Base / Ink-0: `#000000` · Bone-0: `#FAFAF7` · Rule: `#161618`

## Git — NOTHING committed this session
Uncommitted working tree:
- `apps/dashboard/src/components/fog/GexHeatmap.tsx` (candles, axis flip, right
  labels, crosshair)
- `apps/dashboard/package.json` + `pnpm-lock.yaml` (added `regl ^2.1.1`)
- `HANDOFF.md` (this file)
- Deep-color doc syncs: `docs/02-locked-contract.md`, `docs/09-roadmap.md`,
  `docs/reference/{Stitching-Guide,PRD-Gabungan,Build-Playbook-PerFase}.md`,
  `docs/research/verified/README.md`
- `.gitignore` rule for `data/cache/` + `public/data/` already committed in `f0ee1fb`.
- Branch convention so far: committed straight to `main` per user.

## Engine files — DO NOT touch without tests
- `services/engine/src/engine/fog.py`
- `services/engine/src/engine/feed/historical.py`
- `services/engine/tests/test_historical.py` (15 tests pass)
