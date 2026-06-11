"use client";

import { useEffect, useRef, useState } from "react";
import {
  HEATMAP_FRAGMENT_SRC,
  HEATMAP_VERTEX_SRC,
} from "../../lib/heatmap/shaders";
import { hexToRgb } from "../../lib/heatmap/oklab";
import type { Field2D } from "../../lib/heatmap/field-2d";

export interface HeatmapCanvasProps {
  field: Field2D;
  /** sRGB hex anchors (low=turquoise, mid=black|white, high=crimson). */
  stops: { low: string; mid: string; high: string };
  /** true = block (nearest texel), false = smooth interpolation. */
  block: boolean;
  className?: string;
}

function compileShader(
  gl: WebGL2RenderingContext,
  type: number,
  src: string,
): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, src);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error("heatmap shader compile failed:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(gl: WebGL2RenderingContext): WebGLProgram | null {
  const vert = compileShader(gl, gl.VERTEX_SHADER, HEATMAP_VERTEX_SRC);
  const frag = compileShader(gl, gl.FRAGMENT_SHADER, HEATMAP_FRAGMENT_SRC);
  if (!vert || !frag) return null;
  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vert);
  gl.attachShader(program, frag);
  gl.linkProgram(program);
  gl.deleteShader(vert);
  gl.deleteShader(frag);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error("heatmap program link failed:", gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

/**
 * WebGL2 heatmap renderer. Uploads the 2D field as an R32F texture and maps
 * each texel through the locked OKLab ramp in the fragment shader. Handles
 * devicePixelRatio + container resize; falls back to a message if WebGL2 or the
 * float-texture extension is unavailable.
 */
export function HeatmapCanvas({ field, stops, block, className }: HeatmapCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  // Persistent GL objects across renders.
  const glRef = useRef<WebGL2RenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const textureRef = useRef<WebGLTexture | null>(null);
  const uniformsRef = useRef<Record<string, WebGLUniformLocation | null>>({});
  // Whether OES_texture_float_linear is active (else LINEAR-filtering an R32F
  // texture yields an incomplete texture that samples 0 everywhere).
  const floatLinearRef = useRef<boolean>(false);

  // One-time GL init.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl2", {
      antialias: false,
      premultipliedAlpha: false,
    });
    if (!gl) {
      setFailed("WebGL2 is not available in this browser.");
      return;
    }
    // Enable the float-texture extensions. Each getExtension() call ACTIVATES
    // the extension, so they must be called unconditionally (not short-circuited
    // in an `&&`). OES_texture_float_linear is required to LINEAR-filter the R32F
    // field texture; without it the texture is incomplete and samples return 0
    // everywhere (the whole field renders as the ramp's value-0 color).
    gl.getExtension("EXT_color_buffer_float");
    const floatLinear = gl.getExtension("OES_texture_float_linear");
    floatLinearRef.current = !!floatLinear;
    const program = createProgram(gl);
    if (!program) {
      setFailed("Failed to compile the heatmap shaders.");
      return;
    }
    gl.useProgram(program);

    // Fullscreen quad (two triangles) with UVs.
    const quad = new Float32Array([
      // x, y,   u, v
      -1, -1, 0, 0,
      1, -1, 1, 0,
      -1, 1, 0, 1,
      -1, 1, 0, 1,
      1, -1, 1, 0,
      1, 1, 1, 1,
    ]);
    const vbo = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
    gl.bufferData(gl.ARRAY_BUFFER, quad, gl.STATIC_DRAW);
    const posLoc = gl.getAttribLocation(program, "a_pos");
    const uvLoc = gl.getAttribLocation(program, "a_uv");
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 16, 0);
    gl.enableVertexAttribArray(uvLoc);
    gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 16, 8);

    const texture = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    glRef.current = gl;
    programRef.current = program;
    textureRef.current = texture;
    uniformsRef.current = {
      u_field: gl.getUniformLocation(program, "u_field"),
      u_stopLow: gl.getUniformLocation(program, "u_stopLow"),
      u_stopMid: gl.getUniformLocation(program, "u_stopMid"),
      u_stopHigh: gl.getUniformLocation(program, "u_stopHigh"),
      u_gridX: gl.getUniformLocation(program, "u_gridX"),
      u_gridY: gl.getUniformLocation(program, "u_gridY"),
      u_block: gl.getUniformLocation(program, "u_block"),
      u_focusX: gl.getUniformLocation(program, "u_focusX"),
    };
    gl.uniform1i(uniformsRef.current.u_field ?? null, 0);

    return () => {
      gl.deleteProgram(program);
      gl.deleteTexture(texture);
      gl.deleteBuffer(vbo);
      glRef.current = null;
    };
  }, []);

  // Draw whenever field/stops/block change, and on resize.
  useEffect(() => {
    const gl = glRef.current;
    const canvas = canvasRef.current;
    const u = uniformsRef.current;
    if (!gl || !canvas || failed) return;

    const draw = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      const w = Math.max(1, Math.floor(rect.width * dpr));
      const h = Math.max(1, Math.floor(rect.height * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      gl.viewport(0, 0, canvas.width, canvas.height);

      // Upload field as a single-channel float texture. LINEAR (smooth) is only
      // safe when OES_texture_float_linear is active; otherwise fall back to
      // NEAREST so the texture stays complete (never samples 0 everywhere).
      const wantLinear = !block && floatLinearRef.current;
      const filter = wantLinear ? gl.LINEAR : gl.NEAREST;
      gl.bindTexture(gl.TEXTURE_2D, textureRef.current);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.R32F,
        field.width,
        field.height,
        0,
        gl.RED,
        gl.FLOAT,
        field.data,
      );

      const low = hexToRgb(stops.low);
      const mid = hexToRgb(stops.mid);
      const high = hexToRgb(stops.high);
      gl.uniform3f(u.u_stopLow ?? null, low[0], low[1], low[2]);
      gl.uniform3f(u.u_stopMid ?? null, mid[0], mid[1], mid[2]);
      gl.uniform3f(u.u_stopHigh ?? null, high[0], high[1], high[2]);
      gl.uniform1f(u.u_gridX ?? null, field.width);
      gl.uniform1f(u.u_gridY ?? null, field.height);
      gl.uniform1f(u.u_block ?? null, block ? 1 : 0);
      gl.uniform1f(u.u_focusX ?? null, field.focusX);

      gl.drawArrays(gl.TRIANGLES, 0, 6);
    };

    draw();
    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [field, stops, block, failed]);

  if (failed) {
    return (
      <div
        className={`flex h-full w-full items-center justify-center bg-bg ${className ?? ""}`}
      >
        <p className="max-w-xs text-center font-display text-caption text-muted">
          {failed} The heatmap needs a WebGL2-capable browser.
        </p>
      </div>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className={`block h-full w-full ${className ?? ""}`}
      aria-label="Dealer exposure heatmap"
    />
  );
}
