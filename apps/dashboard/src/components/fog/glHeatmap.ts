/**
 * glHeatmap — WebGL (regl) renderer for the FOG GEX/DEX heatmap.
 *
 * Produces the SpotGamma TRACE "smoke/glow" look entirely on the GPU:
 *
 *   field (RGBA8-packed, NEAREST)
 *     → fragment shader: manual bilinear decode + diverging colormap
 *     → bloom: bright-pass → separable gaussian blur → additive composite
 *
 * Design notes
 * ------------
 * - The scalar field is small (~90 strikes × 390 minutes), already normalized
 *   to [-1, 1] and edge-extrapolated (no NaN) by the caller. We pack each signed
 *   value into 16 bits across the R (high byte) and G (low byte) channels of an
 *   RGBA8 texture sampled with NEAREST, then reconstruct a *correct* bilinear
 *   value in the shader with four taps. This avoids the OES_texture_float /
 *   OES_texture_float_linear extensions entirely — plain WebGL1 everywhere.
 * - Colormap is the LOCKED deep diverging palette: deep turquoise (positive /
 *   long gamma) → black (neutral) → deep crimson (negative / short gamma), with a
 *   power curve so saturation deepens toward the extremes.
 * - Bloom runs on half-resolution framebuffers (bright-pass → H blur → V blur)
 *   then is added back over the full-res scene. This is the "senter" glow.
 *
 * The renderer only paints the heatmap quad inside the plot rect (via the GL
 * viewport). Contour lines, candles, axes and the crosshair stay on the Canvas2D
 * overlay stacked above this canvas — see GexHeatmap.tsx.
 */

import createREGL from "regl";
import type { Regl, Framebuffer2D, Texture2D, DrawCommand } from "regl";

// LOCKED CONTRACT palette (docs/02-locked-contract.md), 0..1 floats for GLSL.
const TURQUOISE: [number, number, number] = [15 / 255, 181 / 255, 168 / 255]; // #0FB5A8
const CRIMSON: [number, number, number] = [181 / 255, 0 / 255, 46 / 255]; // #B5002E

export interface HeatmapField {
  nT: number; // columns (time bins)
  nP: number; // rows (price levels, row 0 = highest price / top of plot)
  /** length nT*nP, row-major (idx = p*nT + t), normalized to [-1, 1]. */
  data: Float32Array;
}

export interface PlotRect {
  /** CSS-pixel plot rect within the canvas (origin top-left). */
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface RenderOptions {
  /** Saturation power curve (lower = brighter mid-tones). Default 0.7. */
  power?: number;
  /** Luminance above which a pixel feeds the bloom. Default 0.25. */
  bloomThreshold?: number;
  /** Additive bloom strength. Default 1.1. */
  bloomIntensity?: number;
  /** Gaussian blur step in (half-res) texels. Default 1.0. */
  bloomRadius?: number;
}

export interface GLHeatmapHandle {
  /** (Re)upload the field and draw it into the given plot rect. */
  render(field: HeatmapField, plot: PlotRect, dpr: number, opts?: RenderOptions): void;
  /** Release all GPU resources. */
  destroy(): void;
}

// ---- Shaders ---------------------------------------------------------------

// Full-screen triangle-pair; vUv spans the *current viewport* in [0,1] with
// (0,0) at top-left so it matches the field's row-0-on-top convention.
const QUAD_VERT = `
precision highp float;
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = vec2(position.x * 0.5 + 0.5, 1.0 - (position.y * 0.5 + 0.5));
  gl_Position = vec4(position, 0.0, 1.0);
}`;

// Scene pass: decode the packed field with a hand-rolled bilinear filter, then
// map through the diverging colormap. Output is opaque RGB over black.
const SCENE_FRAG = `
precision highp float;
varying vec2 vUv;
uniform sampler2D uField;
uniform vec2 uGrid;     // (nT, nP)
uniform float uPower;
uniform vec3 uPos;      // positive color (turquoise)
uniform vec3 uNeg;      // negative color (crimson)

// Decode one texel (R high byte, G low byte) to signed [-1, 1].
float decode(vec2 uv) {
  vec4 t = texture2D(uField, uv);
  float q = t.r * 255.0 * 256.0 + t.g * 255.0;
  return (q / 65535.0) * 2.0 - 1.0;
}

void main() {
  vec2 grid = uGrid;
  // Texel-center sampling for the four bracketing samples.
  vec2 f = vUv * (grid - 1.0);
  vec2 i0 = floor(f);
  vec2 i1 = min(i0 + 1.0, grid - 1.0);
  vec2 frac = f - i0;

  vec2 t00 = (i0 + 0.5) / grid;
  vec2 t11 = (i1 + 0.5) / grid;

  float v00 = decode(vec2(t00.x, t00.y));
  float v10 = decode(vec2(t11.x, t00.y));
  float v01 = decode(vec2(t00.x, t11.y));
  float v11 = decode(vec2(t11.x, t11.y));

  float vx0 = mix(v00, v10, frac.x);
  float vx1 = mix(v01, v11, frac.x);
  float v = mix(vx0, vx1, frac.y);

  float mag = pow(abs(v), uPower);
  vec3 col = v >= 0.0 ? uPos : uNeg;
  gl_FragColor = vec4(col * mag, 1.0);
}`;

// Bright-pass: keep only pixels whose luminance exceeds the threshold.
const BRIGHT_FRAG = `
precision highp float;
varying vec2 vUv;
uniform sampler2D uScene;
uniform float uThreshold;
void main() {
  vec3 c = texture2D(uScene, vUv).rgb;
  float b = max(c.r, max(c.g, c.b));
  float k = smoothstep(uThreshold, uThreshold + 0.15, b);
  gl_FragColor = vec4(c * k, 1.0);
}`;

// Separable 9-tap gaussian blur; uDir picks the horizontal/vertical axis.
const BLUR_FRAG = `
precision highp float;
varying vec2 vUv;
uniform sampler2D uTex;
uniform vec2 uTexel;   // 1 / fbo size
uniform vec2 uDir;     // (1,0) or (0,1)
uniform float uRadius;
void main() {
  float w[5];
  w[0] = 0.227027; w[1] = 0.194595; w[2] = 0.121622;
  w[3] = 0.054054; w[4] = 0.016216;
  vec3 acc = texture2D(uTex, vUv).rgb * w[0];
  for (int j = 1; j < 5; j++) {
    vec2 off = uTexel * uDir * (float(j) * uRadius);
    acc += texture2D(uTex, vUv + off).rgb * w[j];
    acc += texture2D(uTex, vUv - off).rgb * w[j];
  }
  gl_FragColor = vec4(acc, 1.0);
}`;

// Composite: scene + bloom * intensity, painted to the screen.
const COMPOSITE_FRAG = `
precision highp float;
varying vec2 vUv;
uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform float uIntensity;
void main() {
  vec3 scene = texture2D(uScene, vUv).rgb;
  vec3 bloom = texture2D(uBloom, vUv).rgb;
  gl_FragColor = vec4(scene + bloom * uIntensity, 1.0);
}`;

// ---- Renderer --------------------------------------------------------------

export function createGLHeatmap(canvas: HTMLCanvasElement): GLHeatmapHandle | null {
  let regl: Regl;
  try {
    regl = createREGL({
      canvas,
      attributes: { alpha: true, premultipliedAlpha: false, antialias: false },
    });
  } catch {
    return null;
  }

  const quad = regl.buffer([
    [-1, -1],
    [3, -1],
    [-1, 3],
  ]);

  // Reusable field texture + bloom framebuffers, (re)sized lazily.
  let fieldTex: Texture2D | null = null;
  let sceneFbo: Framebuffer2D | null = null;
  let brightFbo: Framebuffer2D | null = null;
  let blurAFbo: Framebuffer2D | null = null;
  let blurBFbo: Framebuffer2D | null = null;
  let fboW = 0;
  let fboH = 0;
  let bloomW = 0;
  let bloomH = 0;

  const ensureFbos = (w: number, h: number) => {
    if (w === fboW && h === fboH && sceneFbo) return;
    fboW = w;
    fboH = h;
    bloomW = Math.max(1, Math.floor(w / 2));
    bloomH = Math.max(1, Math.floor(h / 2));
    sceneFbo?.destroy();
    brightFbo?.destroy();
    blurAFbo?.destroy();
    blurBFbo?.destroy();
    sceneFbo = regl.framebuffer({ width: w, height: h, colorType: "uint8" });
    brightFbo = regl.framebuffer({ width: bloomW, height: bloomH, colorType: "uint8" });
    blurAFbo = regl.framebuffer({ width: bloomW, height: bloomH, colorType: "uint8" });
    blurBFbo = regl.framebuffer({ width: bloomW, height: bloomH, colorType: "uint8" });
  };

  const scenePass: DrawCommand = regl({
    vert: QUAD_VERT,
    frag: SCENE_FRAG,
    attributes: { position: quad },
    count: 3,
    uniforms: {
      uField: () => fieldTex as Texture2D,
      uGrid: regl.prop<{ grid: [number, number] }, "grid">("grid"),
      uPower: regl.prop<{ power: number }, "power">("power"),
      uPos: TURQUOISE,
      uNeg: CRIMSON,
    },
    framebuffer: regl.prop<{ fbo: Framebuffer2D }, "fbo">("fbo"),
    depth: { enable: false },
  });

  const brightPass: DrawCommand = regl({
    vert: QUAD_VERT,
    frag: BRIGHT_FRAG,
    attributes: { position: quad },
    count: 3,
    uniforms: {
      uScene: () => sceneFbo as Framebuffer2D,
      uThreshold: regl.prop<{ threshold: number }, "threshold">("threshold"),
    },
    framebuffer: regl.prop<{ fbo: Framebuffer2D }, "fbo">("fbo"),
    depth: { enable: false },
  });

  const blurPass: DrawCommand = regl({
    vert: QUAD_VERT,
    frag: BLUR_FRAG,
    attributes: { position: quad },
    count: 3,
    uniforms: {
      uTex: regl.prop<{ tex: Framebuffer2D }, "tex">("tex"),
      uTexel: regl.prop<{ texel: [number, number] }, "texel">("texel"),
      uDir: regl.prop<{ dir: [number, number] }, "dir">("dir"),
      uRadius: regl.prop<{ radius: number }, "radius">("radius"),
    },
    framebuffer: regl.prop<{ fbo: Framebuffer2D }, "fbo">("fbo"),
    depth: { enable: false },
  });

  const compositePass: DrawCommand = regl({
    vert: QUAD_VERT,
    frag: COMPOSITE_FRAG,
    attributes: { position: quad },
    count: 3,
    uniforms: {
      uScene: () => sceneFbo as Framebuffer2D,
      uBloom: () => blurBFbo as Framebuffer2D,
      uIntensity: regl.prop<{ intensity: number }, "intensity">("intensity"),
    },
    viewport: regl.prop<{ viewport: { x: number; y: number; width: number; height: number } }, "viewport">("viewport"),
    depth: { enable: false },
  });

  // Pack a signed [-1,1] field into an RGBA8 buffer (R high, G low byte).
  const packField = (field: HeatmapField): Uint8Array => {
    const { nT, nP, data } = field;
    const out = new Uint8Array(nT * nP * 4);
    for (let idx = 0; idx < nT * nP; idx++) {
      const v = data[idx];
      const u = Math.min(1, Math.max(0, v * 0.5 + 0.5));
      const q = Math.round(u * 65535);
      const o = idx * 4;
      out[o] = (q >> 8) & 0xff;
      out[o + 1] = q & 0xff;
      out[o + 2] = 0;
      out[o + 3] = 255;
    }
    return out;
  };

  const render = (field: HeatmapField, plot: PlotRect, dpr: number, opts: RenderOptions = {}) => {
    const power = opts.power ?? 0.7;
    const threshold = opts.bloomThreshold ?? 0.25;
    const intensity = opts.bloomIntensity ?? 1.1;
    const radius = opts.bloomRadius ?? 1.0;

    const dw = canvas.width; // device pixels
    const dh = canvas.height;
    if (dw === 0 || dh === 0) return;
    ensureFbos(dw, dh);

    // Upload / refresh the packed field texture.
    const packed = packField(field);
    if (fieldTex) {
      fieldTex({
        width: field.nT,
        height: field.nP,
        data: packed,
        format: "rgba",
        type: "uint8",
        mag: "nearest",
        min: "nearest",
        wrapS: "clamp",
        wrapT: "clamp",
      });
    } else {
      fieldTex = regl.texture({
        width: field.nT,
        height: field.nP,
        data: packed,
        format: "rgba",
        type: "uint8",
        mag: "nearest",
        min: "nearest",
        wrapS: "clamp",
        wrapT: "clamp",
      });
    }

    // Device-pixel plot viewport. GL's origin is bottom-left, so flip the
    // CSS top-down `plot.top` into a bottom-up y.
    const vp = {
      x: Math.round(plot.left * dpr),
      y: Math.round(dh - (plot.top + plot.height) * dpr),
      width: Math.round(plot.width * dpr),
      height: Math.round(plot.height * dpr),
    };

    // Clear everything to opaque black first.
    regl.clear({ color: [0, 0, 0, 1], depth: 1 });

    // 1) Scene → sceneFbo (only inside the plot viewport; rest stays black).
    sceneFbo!.use(() => {
      regl.clear({ color: [0, 0, 0, 1] });
      regl({ viewport: vp })(() => {
        scenePass({ grid: [field.nT, field.nP], power, fbo: sceneFbo! });
      });
    });

    // 2) Bright-pass (full half-res framebuffer).
    brightPass({ threshold, fbo: brightFbo! });

    // 3) Separable blur: H (bright → blurA), then V (blurA → blurB).
    const texel: [number, number] = [1 / bloomW, 1 / bloomH];
    blurPass({ tex: brightFbo!, texel, dir: [1, 0], radius, fbo: blurAFbo! });
    blurPass({ tex: blurAFbo!, texel, dir: [0, 1], radius, fbo: blurBFbo! });

    // 4) Composite scene + bloom into the same plot viewport on screen.
    compositePass({ intensity, viewport: vp });
  };

  const destroy = () => {
    fieldTex?.destroy();
    sceneFbo?.destroy();
    brightFbo?.destroy();
    blurAFbo?.destroy();
    blurBFbo?.destroy();
    quad.destroy();
    regl.destroy();
  };

  return { render, destroy };
}
