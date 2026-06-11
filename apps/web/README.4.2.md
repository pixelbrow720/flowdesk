# FlowDesk — Fase 4.2: WebGL heatmap renderer (field projection)

The centerpiece of the dashboard: a WebGL2 heatmap that renders
`snapshot.field` as a TRACE-style gamma/delta exposure field, with the locked
turquoise→(black|white)→crimson ramp interpolated **in OKLab inside the
fragment shader**. Renders entirely from the mock snapshot — no backend.

## Prerequisites & versions

- Node `>=20 <21` (machine used Node 24; `.nvmrc` present), pnpm `9.7.0` via corepack.
- No new runtime dependency — raw **WebGL2** (no regl), so nothing to pin beyond
  what 4.1 already added.

## Local run

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/heatmap   standalone heatmap (instrument + theme + basis + smooth/block)
```

## Manual verification checklist

- [x] `pnpm --filter @flowdesk/web typecheck` — clean (strict + noUncheckedIndexedAccess).
- [x] `pnpm --filter @flowdesk/web lint` — no ESLint warnings/errors.
- [x] `pnpm --filter @flowdesk/web build` — compiles; `/preview/heatmap` prerenders.
- [x] **Renders in a real browser (Playwright + chromium)**: WebGL2 context
      acquired, canvas DPR-sized (1072×654 @ DPR 2), no fallback shown, zero
      console errors (the only 404 is `/favicon.ico`, unrelated).
- [x] Screenshot confirms a smooth turquoise→black→crimson field (dark) — data-art,
      not a chart-library default; colorbar labeled "Gamma ($ Notional)".
- [x] Gamma/Delta basis toggle switches the rendered array (wired to the store).
- [x] Smooth/block toggle switches texture filtering + texel snapping.
- [x] Theme switch swaps only the mid ramp anchor (black↔white); ends stay locked.

## File list (added in this task)

```
apps/web/
  lib/heatmap/
    oklab.ts        # sRGB<->OKLab, OKLab ramp sampler, CSS-gradient helper (canonical ref)
    shaders.ts      # GLSL ES 3.00 vertex + fragment; OKLab ramp mirrors oklab.ts exactly
    field-2d.ts     # 1D snapshot field -> mock 2D (time x price) + symmetric [0,1] normalization
  components/heatmap/
    heatmap-canvas.tsx  # WebGL2 renderer: R32F texture upload, DPR/resize, smooth|block, fallback
    colorbar.tsx        # OKLab-sampled CSS gradient, labeled per basis
    heatmap.tsx         # wrapper wired to the store (basis + smooth/block)
    index.ts            # barrel
  app/preview/heatmap/page.tsx   # standalone preview route
```

## How the color pipeline works

- The field is pre-normalized on the CPU (`field-2d.ts`) symmetrically around
  zero to `[0,1]`: **0.0 = strongest positive (turquoise), 0.5 = neutral
  (mid anchor), 1.0 = strongest negative (crimson)**, using the max abs
  magnitude so neutral always lands on the mid anchor.
- It is uploaded as a single-channel **R32F** texture. The fragment shader
  (`shaders.ts`) samples the value and maps it through the 3-stop ramp,
  interpolating the two relevant anchors **in OKLab** (Björn Ottosson's matrices)
  then converting back to sRGB. This matches `oklab.ts` byte-for-byte, so the DOM
  colorbar and the GPU field are identical.
- **smooth** = linear texture filtering; **block** = nearest filtering + the
  shader snaps UVs to texel centers so each minute/strike cell is a solid block.

## Assumptions

- **2D field is synthesized for offline dev.** The Snapshot `field` is 1D (one
  value per strike for the current minute). The heatmap needs time×price, so
  `buildMockField2D` drifts the 1D profile deterministically over `minutes`
  columns (no `Math.random`, so SSR/client agree); the newest column equals the
  snapshot's current field. In LIVE use the worker appends one real column per
  minute (4.7 wires the realtime feed) — only the field source changes, not the
  renderer.
- **Raw WebGL2 over regl.** Avoids a new dependency and keeps full control of the
  shader. Requires WebGL2; a token-styled fallback message renders when it (or a
  needed float-texture extension) is unavailable.
- **Colorbar shows ± max abs magnitude** (the normalization bound), compact-formatted.
- DELTA reuses the same signed ramp as GAMMA (the locked ramp is basis-agnostic);
  the colorbar label switches to "Delta ($ Notional)".
- No `TODO-FROM-OWNER` items for this task.
```
