/**
 * OKLab color conversions + perceptual ramp sampling.
 *
 * The heatmap ramp (PRD #2, locked) interpolates between sRGB anchor stops in
 * OKLab space — NOT naive sRGB — so the gradient is perceptually uniform and
 * avoids muddy mid-tones. This TS implementation is the canonical reference; the
 * GLSL in `shaders.ts` mirrors it exactly (same matrices, same gamma, same
 * per-stop OKLab interpolation) so the WebGL field and the DOM colorbar match.
 *
 * Reference: Björn Ottosson, "A perceptual color space for image processing"
 * (https://bottosson.github.io/posts/oklab/).
 */

export type RGB = readonly [number, number, number]; // each channel 0..1
export type Lab = readonly [number, number, number]; // OKLab L, a, b

/** sRGB gamma-encoded channel -> linear. */
function srgbToLinear(c: number): number {
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** Linear channel -> sRGB gamma-encoded. */
function linearToSrgb(c: number): number {
  return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
}

/** Parse "#rrggbb" -> sRGB [0..1] triplet. */
export function hexToRgb(hex: string): RGB {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  return [r, g, b];
}

/** sRGB [0..1] -> "#rrggbb". Clamps out-of-gamut channels. */
export function rgbToHex(rgb: RGB): string {
  const to = (c: number) =>
    Math.max(0, Math.min(255, Math.round(c * 255)))
      .toString(16)
      .padStart(2, "0");
  return `#${to(rgb[0])}${to(rgb[1])}${to(rgb[2])}`;
}

/** Gamma-encoded sRGB -> OKLab. */
export function srgbToOklab(rgb: RGB): Lab {
  const r = srgbToLinear(rgb[0]);
  const g = srgbToLinear(rgb[1]);
  const b = srgbToLinear(rgb[2]);

  const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
  const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
  const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;

  const l_ = Math.cbrt(l);
  const m_ = Math.cbrt(m);
  const s_ = Math.cbrt(s);

  return [
    0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_,
    1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_,
    0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_,
  ];
}

/** OKLab -> gamma-encoded sRGB (clamped to [0,1]). */
export function oklabToSrgb(lab: Lab): RGB {
  const L = lab[0];
  const a = lab[1];
  const b = lab[2];

  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.291485548 * b;

  const l = l_ ** 3;
  const m = m_ ** 3;
  const s = s_ ** 3;

  const r = linearToSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s);
  const g = linearToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s);
  const bb = linearToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s);

  return [
    Math.max(0, Math.min(1, r)),
    Math.max(0, Math.min(1, g)),
    Math.max(0, Math.min(1, bb)),
  ];
}

/** A ramp anchor: sRGB color at normalized position `stop` in [0,1]. */
export interface RampStop {
  readonly stop: number;
  readonly color: string; // "#rrggbb"
}

/**
 * Sample a 3-stop (or N-stop) ramp at `t` in [0,1], interpolating in OKLab.
 * Anchors must be sorted ascending by `stop`. Returns sRGB [0..1].
 */
export function sampleRampOklab(stops: readonly RampStop[], t: number): RGB {
  const clamped = Math.max(0, Math.min(1, t));
  const first = stops[0];
  const last = stops[stops.length - 1];
  if (first === undefined || last === undefined) return [0, 0, 0];
  if (clamped <= first.stop) return hexToRgb(first.color);
  if (clamped >= last.stop) return hexToRgb(last.color);

  for (let i = 0; i < stops.length - 1; i++) {
    const lo = stops[i];
    const hi = stops[i + 1];
    if (lo === undefined || hi === undefined) break;
    if (clamped >= lo.stop && clamped <= hi.stop) {
      const span = hi.stop - lo.stop || 1;
      const f = (clamped - lo.stop) / span;
      const labLo = srgbToOklab(hexToRgb(lo.color));
      const labHi = srgbToOklab(hexToRgb(hi.color));
      const mix: Lab = [
        labLo[0] + (labHi[0] - labLo[0]) * f,
        labLo[1] + (labHi[1] - labLo[1]) * f,
        labLo[2] + (labHi[2] - labLo[2]) * f,
      ];
      return oklabToSrgb(mix);
    }
  }
  return hexToRgb(last.color);
}

/** Render the ramp as a CSS linear-gradient string sampled in OKLab (N steps). */
export function rampToCssGradient(
  stops: readonly RampStop[],
  steps = 24,
  angle = "to top",
): string {
  const parts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const rgb = sampleRampOklab(stops, t);
    parts.push(`${rgbToHex(rgb)} ${(t * 100).toFixed(1)}%`);
  }
  return `linear-gradient(${angle}, ${parts.join(", ")})`;
}
