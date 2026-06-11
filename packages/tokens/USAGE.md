# @flowdesk/tokens — USAGE (DO / DON'T)

Tokens are the **only** allowed source of colors, spacing, and type. Components
MUST consume them via the Tailwind preset, the CSS variables, or the TS
constants. **Hard-coded hex / px in components is forbidden.**

## Import

```ts
// App root (e.g. apps/web/app/layout.tsx)
import "@flowdesk/tokens/fonts.css";   // @font-face for Space Grotesk + JetBrains Mono
import "@flowdesk/tokens/tokens.css";  // CSS variables (:root dark, [data-theme=light])
```

```ts
// tailwind.config.ts
import flowdeskPreset from "@flowdesk/tokens/tailwind-preset";
export default { presets: [flowdeskPreset], content: ["./app/**/*.{ts,tsx}"] };
```

```ts
// Raw values when you need them outside CSS (e.g. WebGL heatmap shaders)
import { TURQUOISE, CRIMSON, heatmap } from "@flowdesk/tokens";
```

## Color utilities (from the preset)

| Role | Utility | Resolves to |
| --- | --- | --- |
| positive / support | `text-positive` `bg-support` | turquoise `#40E0D0` (fixed) |
| negative / resistance | `text-negative` `bg-resistance` | crimson `#E0183C` (fixed) |
| brand turquoise/crimson | `bg-turquoise` `text-crimson` | locked hex (fixed) |
| neutral chrome | `bg-gray-950` … `text-gray-50` | gray ramp (fixed) |
| page background | `bg-bg` | `var(--color-bg)` (theme-aware) |
| panel surface | `bg-surface` | `var(--color-surface)` (theme-aware) |
| hairline border | `border-border` | `var(--color-border)` (theme-aware) |
| primary text | `text-fg` | `var(--color-text-primary)` (theme-aware) |
| muted text | `text-muted` | `var(--color-text-muted)` (theme-aware) |

> `text-primary` → `text-fg`, `text-muted` → `text-muted`. Theme-aware roles flip
> automatically when `[data-theme="light"]` is set on a parent.

## DO

- ✅ **Numbers always in JetBrains Mono.** Use `font-mono` on every figure, price,
  GEX/DEX value, axis label, and clock.
- ✅ **`tabular-nums` on all figures** so digits align in columns:
  `class="font-mono tabular-nums"` (or CSS `font-variant-numeric: tabular-nums`).
- ✅ Use the **closed spacing scale** (`p-4 p-8 p-12 p-16 p-24 p-32 p-48 p-64`,
  pixel-valued — see note below).
- ✅ Use **restrained radius**: `rounded-sm` (2px), `rounded` (4px), `rounded-lg`
  (8px). Panels and cards lean toward `sm`/`md`.
- ✅ Use **semantic colors** for meaning: turquoise = positive/support/pinning,
  crimson = negative/resistance/volatile. Never reverse them.
- ✅ Use **glows for data states only**: `shadow-glow-positive` /
  `shadow-glow-negative` to signal regime, not for decoration.
- ✅ Keep motion restrained: `duration-fast|base|slow` with `ease-standard`.
- ✅ Interpolate the **heatmap in OKLab/OKLCH** (perceptual), never naive sRGB.

## DON'T

- ❌ **No Inter.** UI/display = Space Grotesk only; numbers = JetBrains Mono only.
- ❌ **No decorative / wedding-style / script fonts** anywhere.
- ❌ **No generic SaaS purple gradients**, no rainbow, no neon-on-white.
- ❌ **No hard-coded hex or px** in components. If a value is missing, add it to
  `tokens.ts` (+ `tokens.css` + preset) — do not inline it.
- ❌ **No rounded-everything.** No `rounded-full` on cards/buttons; pills are for
  genuine tags/toggles only.
- ❌ **No emoji as icons.**
- ❌ **No centered hero with one big button** cliche (landing rules live in Phase 5).
- ❌ Don't put numbers in the UI font — proportional digits jitter on live updates.

## Spacing note (pixel-valued scale)

This preset maps the eight spacing keys to **literal pixels**, matching the
locked 4px scale: `p-4` = 4px, `p-8` = 8px, … `p-64` = 64px. This intentionally
redefines the numeric spacing keys (default Tailwind treats them as rem). It is
recorded under README → Assumptions. Use only these eight steps; no arbitrary
`p-[13px]` values.
