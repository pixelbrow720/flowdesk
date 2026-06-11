# FlowDesk — Fase 4.1: App shell + design system primitives

Next.js App Router shell for `apps/web` (`@flowdesk/web`), consuming
`@flowdesk/tokens` (design tokens, 0.3) and `@flowdesk/contracts` (Snapshot
contract, 0.2). Establishes the theme system, the token-driven primitive
component library, an offline mock-data layer + store, and a `/preview` gallery.

## Prerequisites & versions

- Node `>=20 <21` (machine used Node 24 — works, but the locked engine field is 20 LTS; `.nvmrc` present).
- pnpm `9.7.0` (via corepack: `corepack pnpm@9.7.0 ...`, or `corepack enable` from an elevated shell once).
- Workspace deps installed from the repo root: `corepack pnpm@9.7.0 install`.

## Local run

```bash
# from repo root
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev       # http://localhost:3000
#   -> /          landing skeleton
#   -> /preview   primitive component gallery (theme toggle dark/light)
```

## Manual verification checklist

- [x] `pnpm --filter @flowdesk/web typecheck` — clean (tsc, strict + noUncheckedIndexedAccess).
- [x] `pnpm --filter @flowdesk/web lint` — no ESLint warnings/errors.
- [x] `pnpm --filter @flowdesk/web build` — compiles; `/`, `/preview` prerender static.
- [x] Mock snapshot validates against the contract: `lib/mock-data.ts` calls
      `parseSnapshot(...)` at module load, so the successful build/prerender of
      `/preview` (which imports the store -> mock-data) proves both ES + NQ
      fixtures satisfy `schema_version 1`.
- [x] Dev/prod server renders `/` and `/preview` (HTTP 200); gallery shows every
      primitive in both themes via the header theme toggle.
- [x] Numbers render in JetBrains Mono + `tabular-nums` (NumberReadout, SegmentedControl).
- [x] No hard-coded hex in components — all color/spacing/radius via the token
      Tailwind preset + `tokens.css` CSS variables.

## File list (added/changed in this task)

```
apps/web/
  package.json                      # + zustand 4.5.4
  tailwind.config.ts                # now uses @flowdesk/tokens/tailwind-preset (was layout-only hex)
  app/
    globals.css                     # imports @tokens/tokens.css; reduced-motion rule; theme-aware bg/fg
    layout.tsx                      # ThemeProvider + no-flash script + pinned font weights
    preview/page.tsx                # NEW — primitive gallery
  components/
    theme-provider.tsx              # NEW — [data-theme] toggle, localStorage flowdesk.theme, default dark
    theme-toggle.tsx                # NEW — segmented dark/light control
    ui/
      button.tsx  icon-button.tsx  segmented-control.tsx  toggle.tsx
      pill.tsx  tooltip.tsx  panel.tsx  divider.tsx  number-readout.tsx
      spinner.tsx  blur-overlay.tsx  index.ts          # NEW — 11 primitives + barrel
  lib/
    cn.ts                           # NEW — className joiner (no dep)
    mock-data.ts                    # NEW — ES+NQ Snapshot fixtures, validated via parseSnapshot
    store.ts                        # NEW — zustand {instrument, snapshot, connectionState, toggles}
```

## Primitives (all token-driven, no hard-coded hex)

`Button`, `IconButton`, `SegmentedControl` (ES|NQ), `Toggle`, `Pill`
(neutral/positive/negative + data-state glow), `Tooltip`, `Panel` (surface +
glass), `Divider`, `NumberReadout` (JetBrains Mono + tabular-nums, optional
signed turquoise/crimson), `Spinner`, `BlurOverlay` (for the NO_DESK/ANON
preview-blur in 4.9).

## Store & defaults (PRD #5)

`useDashboardStore` (zustand) holds `{ instrument, snapshot, connectionState,
profileMetric, heatmapBasis, heatmapSmooth }`. Defaults: instrument **ES**,
**Net GEX**, **Gamma** basis, **smooth** render. Switching instrument swaps in
the validated mock for that instrument until the realtime layer (4.7) overwrites
it. Theme lives in `ThemeProvider` (DOM `[data-theme]` + localStorage), separate
from the data store.

## Assumptions

- **Fonts: `next/font/google`** (Space Grotesk + JetBrains Mono) is kept as the
  loader rather than the self-hosted `@flowdesk/tokens/fonts.css`, because the
  licensed `.woff2` files are not in the repo yet. `next/font` renders the
  correct locked fonts immediately and exposes them as the
  `--font-space-grotesk` / `--font-jetbrains-mono` CSS variables that
  `tailwind.config.ts` binds to. To switch to self-hosting later: drop the
  woff2 files into `apps/web/public/fonts/` (filenames per
  `packages/tokens/fonts/fonts.css`) and import that stylesheet.
- **Tailwind now consumes the token preset** (`@flowdesk/tokens/tailwind-preset`)
  instead of the previous layout-only config that redeclared hex. Theme-aware
  roles (`bg`, `surface`, `border`, `fg`, `muted`) resolve to the `tokens.css`
  CSS variables; locked brand colors (`turquoise`, `crimson`) are literal.
- **`rounded-full`** (Tailwind built-in) is used for the pill/toggle shapes; the
  token radius scale intentionally stops at `lg` (8px) and has no pill radius.
- **Mock field shape** is a smooth signed curve (positive hump at the forward,
  negative wings) chosen only to look like realistic data-art; it is not derived
  from the engine. It is contract-valid (equal-length `price_grid`/`gamma`/`delta`).
- No `TODO-FROM-OWNER` items for this task.
```
