/**
 * GLSL ES 3.00 shaders for the WebGL2 heatmap.
 *
 * The fragment shader maps a normalized field value (sampled from an R32F
 * texture) through the locked heatmap ramp, interpolating between the three
 * sRGB anchor stops in OKLab space. The OKLab math here MIRRORS
 * `lib/heatmap/oklab.ts` byte-for-byte (same matrices, same sRGB gamma, same
 * per-stop interpolation) so the GPU field and the DOM colorbar render
 * identically.
 *
 * Value convention: the field is pre-normalized on the CPU to [0,1] where
 * 0.0 = strongest positive (turquoise), 0.5 = neutral (mid anchor), 1.0 =
 * strongest negative (crimson). Three ramp anchors are passed as uniforms so a
 * theme switch only changes the mid anchor (black<->white).
 */

export const HEATMAP_VERTEX_SRC = `#version 300 es
precision highp float;

// Fullscreen triangle/quad in clip space + matching UVs.
in vec2 a_pos;   // clip-space position, -1..1
in vec2 a_uv;    // texture coords, 0..1
out vec2 v_uv;

void main() {
  v_uv = a_uv;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`;

export const HEATMAP_FRAGMENT_SRC = `#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D u_field;   // R32F, value in [0,1] (0=pos,0.5=neutral,1=neg)
uniform vec3 u_stopLow;      // sRGB anchor at stop 0.0 (turquoise)
uniform vec3 u_stopMid;      // sRGB anchor at stop 0.5 (black/white)
uniform vec3 u_stopHigh;     // sRGB anchor at stop 1.0 (crimson)
uniform float u_gridX;       // field width  (texels) for block snapping
uniform float u_gridY;       // field height (texels)
uniform float u_block;       // 1.0 = block (nearest), 0.0 = smooth (linear-ish)
uniform float u_focusX;      // x in [0,1] of the flashlight source (latest candle)

// ---- sRGB <-> linear (matches oklab.ts) ----
float srgbToLinear(float c) {
  return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4);
}
float linearToSrgb(float c) {
  return c <= 0.0031308 ? 12.92 * c : 1.055 * pow(c, 1.0 / 2.4) - 0.055;
}
vec3 srgbToLinear3(vec3 c) {
  return vec3(srgbToLinear(c.r), srgbToLinear(c.g), srgbToLinear(c.b));
}

// ---- sRGB -> OKLab (matches oklab.ts matrices) ----
vec3 srgbToOklab(vec3 rgb) {
  vec3 lin = srgbToLinear3(rgb);
  float l = 0.4122214708 * lin.r + 0.5363325363 * lin.g + 0.0514459929 * lin.b;
  float m = 0.2119034982 * lin.r + 0.6806995451 * lin.g + 0.1073969566 * lin.b;
  float s = 0.0883024619 * lin.r + 0.2817188376 * lin.g + 0.6299787005 * lin.b;
  float l_ = pow(l, 1.0 / 3.0);
  float m_ = pow(m, 1.0 / 3.0);
  float s_ = pow(s, 1.0 / 3.0);
  return vec3(
    0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
    1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
    0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
  );
}

// ---- OKLab -> sRGB (matches oklab.ts) ----
vec3 oklabToSrgb(vec3 lab) {
  float l_ = lab.x + 0.3963377774 * lab.y + 0.2158037573 * lab.z;
  float m_ = lab.x - 0.1055613458 * lab.y - 0.0638541728 * lab.z;
  float s_ = lab.x - 0.0894841775 * lab.y - 1.2914855480 * lab.z;
  float l = l_ * l_ * l_;
  float m = m_ * m_ * m_;
  float s = s_ * s_ * s_;
  float r = linearToSrgb( 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s);
  float g = linearToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s);
  float b = linearToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s);
  return clamp(vec3(r, g, b), 0.0, 1.0);
}

// Sample the 3-stop ramp at t in [0,1], interpolating in OKLab.
vec3 rampOklab(float t) {
  t = clamp(t, 0.0, 1.0);
  vec3 labLow = srgbToOklab(u_stopLow);
  vec3 labMid = srgbToOklab(u_stopMid);
  vec3 labHigh = srgbToOklab(u_stopHigh);
  vec3 lab;
  if (t < 0.5) {
    lab = mix(labLow, labMid, t / 0.5);
  } else {
    lab = mix(labMid, labHigh, (t - 0.5) / 0.5);
  }
  return oklabToSrgb(lab);
}

void main() {
  vec2 uv = v_uv;
  if (u_block > 0.5) {
    // Snap to the texel center so each minute/strike cell is a solid block.
    uv = (floor(uv * vec2(u_gridX, u_gridY)) + 0.5) / vec2(u_gridX, u_gridY);
  }
  float value = texture(u_field, uv).r;
  vec3 rgb = rampOklab(value);

  // Flashlight: the beam originates at u_focusX (the latest candle, right side)
  // and falls off into the past (left). Magnitude already drives base brightness
  // via the ramp (neutral=black, strong GEX=bright); the beam adds a gentle
  // directional cone so the most recent structure glows brightest and older
  // columns dim — but never to full black, so the field stays readable like a
  // lit topo surface (not a hard spotlight).
  float d = max(u_focusX - v_uv.x, 0.0);
  float beam = 1.0 - smoothstep(0.0, max(u_focusX, 0.0001), d);
  rgb *= mix(0.55, 1.0, beam);

  fragColor = vec4(rgb, 1.0);
}
`;
