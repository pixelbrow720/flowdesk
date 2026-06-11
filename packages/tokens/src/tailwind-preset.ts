/**
 * FlowDesk Tailwind preset — maps design tokens into `theme.extend`.
 * `apps/web` consumes this via `presets: [flowdeskPreset]`.
 *
 * Theme-aware semantic colors (bg/surface/border/fg/muted) resolve to CSS
 * custom properties defined in `tokens.css`, so they follow the active
 * `:root` (dark) / `[data-theme="light"]` theme. Fixed brand colors
 * (turquoise/crimson and the gray ramp) are emitted as literal hex.
 */
import type { Config } from "tailwindcss";

import {
  duration,
  easing,
  fontFamily,
  gray,
  palette,
  radius,
  shadow,
  spacing,
  typeScale,
} from "./tokens";

const preset = {
  content: [],
  theme: {
    extend: {
      colors: {
        // Fixed brand palette (locked, theme-independent).
        turquoise: palette.turquoise,
        crimson: palette.crimson,
        base: palette.black,
        white: palette.white,
        gray,
        // Semantic, locked-direction roles (fixed across themes).
        positive: palette.turquoise,
        negative: palette.crimson,
        support: palette.turquoise,
        resistance: palette.crimson,
        // Theme-aware roles (resolve via CSS variables from tokens.css).
        bg: "var(--color-bg)",
        surface: "var(--color-surface)",
        border: "var(--color-border)",
        // text-primary -> `fg`, text-muted -> `muted` (clean utility names).
        fg: "var(--color-text-primary)",
        muted: "var(--color-text-muted)",
      },
      // Closed 4px spacing scale, keyed by literal pixel value (see USAGE).
      spacing: {
        4: spacing[4],
        8: spacing[8],
        12: spacing[12],
        16: spacing[16],
        24: spacing[24],
        32: spacing[32],
        48: spacing[48],
        64: spacing[64],
      },
      borderRadius: {
        none: radius.none,
        sm: radius.sm,
        DEFAULT: radius.md,
        md: radius.md,
        lg: radius.lg,
      },
      fontFamily: {
        // UI/display = Space Grotesk; mono = JetBrains Mono. Never Inter.
        sans: [...fontFamily.ui],
        display: [...fontFamily.ui],
        mono: [...fontFamily.mono],
      },
      fontSize: {
        display: [
          typeScale.display.size,
          { lineHeight: typeScale.display.lineHeight, letterSpacing: typeScale.display.tracking },
        ],
        h1: [
          typeScale.h1.size,
          { lineHeight: typeScale.h1.lineHeight, letterSpacing: typeScale.h1.tracking },
        ],
        h2: [
          typeScale.h2.size,
          { lineHeight: typeScale.h2.lineHeight, letterSpacing: typeScale.h2.tracking },
        ],
        body: [
          typeScale.body.size,
          { lineHeight: typeScale.body.lineHeight, letterSpacing: typeScale.body.tracking },
        ],
        caption: [
          typeScale.caption.size,
          { lineHeight: typeScale.caption.lineHeight, letterSpacing: typeScale.caption.tracking },
        ],
        mono: [
          typeScale.mono.size,
          { lineHeight: typeScale.mono.lineHeight, letterSpacing: typeScale.mono.tracking },
        ],
      },
      transitionDuration: {
        fast: duration.fast,
        base: duration.base,
        slow: duration.slow,
        120: duration.fast,
        180: duration.base,
        240: duration.slow,
      },
      transitionTimingFunction: {
        standard: easing.standard,
        decelerate: easing.decelerate,
        accelerate: easing.accelerate,
      },
      boxShadow: {
        "elevation-1": shadow.elevation1,
        "elevation-2": shadow.elevation2,
        "glow-positive": shadow.glowPositive,
        "glow-negative": shadow.glowNegative,
      },
    },
  },
} satisfies Partial<Config>;

export default preset;
