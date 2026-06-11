/**
 * FlowDesk design tokens — the SINGLE allowed source of colors, spacing, and
 * type for every UI surface. Hard-coded hex/spacing in components is forbidden;
 * import from here (or use the Tailwind preset / CSS variables generated from
 * these same values).
 *
 * Locked contract (PRD #0 §7): turquoise #40E0D0 = positive/support,
 * crimson #E0183C = negative/resistance, dark base #000000. Fonts: Space Grotesk
 * (UI/display) + JetBrains Mono (numbers). NEVER Inter, never decorative.
 *
 * `tokens.css` mirrors these values as CSS custom properties (dark `:root` +
 * `[data-theme="light"]`); `tailwind-preset.ts` maps them into `theme.extend`.
 * Keep all three in sync.
 */

/* ───────────────────────── Core palette (locked) ──────────────────────── */

/** Positive / support. Locked. */
export const TURQUOISE = "#40E0D0" as const;
/** Negative / resistance. Locked. */
export const CRIMSON = "#E0183C" as const;
/** Dark base background. Locked. */
export const BASE_BLACK = "#000000" as const;
/** Pure white (light-theme base / heatmap light midpoint). */
export const WHITE = "#FFFFFF" as const;

/**
 * Neutral monochrome ramp for dark UI chrome (cool-neutral, slightly blue).
 * 50 = lightest, 950 = near-black. Used for surfaces, borders, and text.
 */
export const gray = {
  50: "#F5F6F7",
  100: "#E7E9EB",
  200: "#CCD0D4",
  300: "#AAB1B8",
  400: "#838B93",
  500: "#626A72",
  600: "#4A5158",
  700: "#363B41",
  800: "#23272B",
  900: "#15181B",
  950: "#0A0C0D",
} as const;

/** Raw palette (theme-independent literal values). */
export const palette = {
  turquoise: TURQUOISE,
  crimson: CRIMSON,
  black: BASE_BLACK,
  white: WHITE,
  gray,
} as const;

/* ─────────────────────── Semantic aliases (per theme) ──────────────────── */

/** Semantic color roles for the DEFAULT dark theme. */
export const semanticDark = {
  positive: TURQUOISE,
  negative: CRIMSON,
  support: TURQUOISE,
  resistance: CRIMSON,
  bg: BASE_BLACK,
  surface: gray[950],
  border: gray[800],
  textPrimary: gray[50],
  textMuted: gray[400],
} as const;

/** Semantic color roles for the light theme. positive/negative stay locked. */
export const semanticLight = {
  positive: TURQUOISE,
  negative: CRIMSON,
  support: TURQUOISE,
  resistance: CRIMSON,
  bg: WHITE,
  surface: gray[50],
  border: gray[200],
  textPrimary: gray[950],
  textMuted: gray[500],
} as const;

/* ───────────────────────────── Spacing (4px base) ────────────────────────── */

/**
 * Spacing scale, 4px base. Keyed by literal pixel value.
 * Intentionally a CLOSED 8-step scale — no arbitrary values in components.
 */
export const spacing = {
  4: "4px",
  8: "8px",
  12: "12px",
  16: "16px",
  24: "24px",
  32: "32px",
  48: "48px",
  64: "64px",
} as const;

/* ────────────────────────────── Radius (restrained) ─────────────────────── */

/** Border radii. Restrained: 2 / 4 / 8 only (NOT pill-everything). */
export const radius = {
  none: "0px",
  sm: "2px",
  md: "4px",
  lg: "8px",
} as const;

/* ───────────────────────────────── Typography ───────────────────────────── */

/** Font family stacks. UI/display = Space Grotesk; numbers/mono = JetBrains Mono. */
export const fontFamily = {
  ui: ["\"Space Grotesk\"", "ui-sans-serif", "system-ui", "sans-serif"],
  mono: [
    "\"JetBrains Mono\"",
    "ui-monospace",
    "SFMono-Regular",
    "Menlo",
    "monospace",
  ],
} as const;

/** Self-hosted font weights that MUST be provided as .woff2 (see README/fonts). */
export const fontWeights = {
  ui: [400, 500, 600, 700],
  mono: [400, 500],
} as const;

/** One type-scale step: size + line-height + default weight + letter-spacing. */
export interface TypeStep {
  /** Font size in rem. */
  readonly size: string;
  /** Unitless line-height. */
  readonly lineHeight: string;
  /** Default font weight. */
  readonly weight: number;
  /** Letter-spacing (tracking). */
  readonly tracking: string;
}

/** Type scale (rem-based). `mono` is the canonical size for figures. */
export const typeScale = {
  display: { size: "3.5rem", lineHeight: "1.05", weight: 700, tracking: "-0.02em" },
  h1: { size: "2.25rem", lineHeight: "1.1", weight: 600, tracking: "-0.015em" },
  h2: { size: "1.5rem", lineHeight: "1.2", weight: 600, tracking: "-0.01em" },
  body: { size: "1rem", lineHeight: "1.5", weight: 400, tracking: "0em" },
  caption: { size: "0.8125rem", lineHeight: "1.4", weight: 400, tracking: "0.01em" },
  mono: { size: "0.875rem", lineHeight: "1.4", weight: 500, tracking: "0em" },
} as const satisfies Record<string, TypeStep>;

/* ─────────────────────────────────── Motion ─────────────────────────────── */

/** Animation durations. Restrained motion only. */
export const duration = {
  fast: "120ms",
  base: "180ms",
  slow: "240ms",
} as const;

/** Easing curves. */
export const easing = {
  standard: "cubic-bezier(0.4, 0, 0.2, 1)",
  decelerate: "cubic-bezier(0, 0, 0.2, 1)",
  accelerate: "cubic-bezier(0.4, 0, 1, 1)",
} as const;

/* ──────────────────────────── Shadows & data-state glows ────────────────── */

/** Elevation shadows + subtle turquoise/crimson glows for data states. */
export const shadow = {
  elevation1: "0 1px 2px rgba(0, 0, 0, 0.6)",
  elevation2: "0 4px 16px rgba(0, 0, 0, 0.7)",
  /** Positive / pinning state glow (turquoise). */
  glowPositive:
    "0 0 0 1px rgba(64, 224, 208, 0.35), 0 0 16px rgba(64, 224, 208, 0.25)",
  /** Negative / volatile state glow (crimson). */
  glowNegative:
    "0 0 0 1px rgba(224, 24, 60, 0.35), 0 0 16px rgba(224, 24, 60, 0.25)",
} as const;

/* ────────────────────────────── Heatmap ramps ────────────────────────── */

/** A single heatmap ramp stop: position in [0,1] mapped to a color. */
export interface RampStop {
  /** Normalized position along the ramp, 0..1. */
  readonly stop: number;
  /** sRGB hex anchor color at this stop. */
  readonly color: string;
}

/**
 * Heatmap ramps (locked direction).
 * - dark:  turquoise → black → crimson
 * - light: turquoise → white → crimson
 *
 * IMPORTANT: these are sRGB ANCHORS only. Interpolation between stops MUST be
 * performed in a perceptual space (OKLab / OKLCH), not naive sRGB, so the ramp
 * is perceptually uniform and avoids muddy mid-tones. See `tokens.css`.
 */
export const heatmap = {
  dark: [
    { stop: 0, color: TURQUOISE },
    { stop: 0.5, color: BASE_BLACK },
    { stop: 1, color: CRIMSON },
  ],
  light: [
    { stop: 0, color: TURQUOISE },
    { stop: 0.5, color: WHITE },
    { stop: 1, color: CRIMSON },
  ],
} as const satisfies Record<"dark" | "light", readonly RampStop[]>;

/* ─────────────────────────────── Aggregate ──────────────────────────── */

/** Single aggregate of every token group. */
export const tokens = {
  palette,
  semanticDark,
  semanticLight,
  spacing,
  radius,
  fontFamily,
  fontWeights,
  typeScale,
  duration,
  easing,
  shadow,
  heatmap,
} as const;

export type Tokens = typeof tokens;
export type GrayShade = keyof typeof gray;
export type SpacingStep = keyof typeof spacing;
export type RadiusName = keyof typeof radius;
export type TypeScaleName = keyof typeof typeScale;
