"use client";

/**
 * ArcPanel — 3D implied-volatility surface renderer (Three.js).
 *
 * Renders σ(K, session-time) as a real WebGL surface mesh built from per-minute
 * SVI fits. Supports mouse-orbit (left-drag), pan (right-drag), wheel-zoom, and
 * an animated "now" cursor plane at the current replay playhead.
 *
 * Why three.js: the dependency-light Canvas2D axonometric approach was technically
 * a wireframe skeleton — proper 3D (shading, axes, depth, click-to-inspect) needs
 * a real WebGL renderer. three.js (~600 kB minified+gzipped, tree-shakeable) is
 * the right tool for this single 3D lens.
 */

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { buildVolSurface, surfaceIVRange, type SnapshotLike } from "./arcSurface";

export interface ArcPanelProps {
  frames: SnapshotLike[];
  /** Playhead minute_index for the "now" cursor plane. -1 hides the cursor. */
  playheadMinute: number;
  /** Bin frames into N-minute buckets to smooth per-minute SVI jitter (default 1). */
  binMinutes?: number;
  className?: string;
}

export function ArcPanel({
  frames,
  playheadMinute,
  binMinutes = 1,
  className = "flex-1",
}: ArcPanelProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const cursorMeshRef = useRef<THREE.Mesh | null>(null);

  // Build the surface grid once per frames/bin change.
  const surface = useMemo(
    () => buildVolSurface(frames, 0.03, 50, binMinutes),
    [frames, binMinutes],
  );
  // 95th-percentile cap: the 0DTE wing IV (σ = sqrt(w/T)) blows up as T → 0 in
  // the last minutes; an un-clamped max would compress the whole surface relief.
  const { min: ivMin, max: ivMax } = useMemo(
    () => surfaceIVRange(surface.grid, 0.95),
    [surface],
  );

  // Initial playhead value (captured at mount so we don't restart the scene).
  const initialPlayhead = useRef(playheadMinute).current;

  // (Re)build the 3D scene whenever the surface changes (i.e. when frames
  // arrive via useTerminalFeed → useLiveSnapshots/useReplaySnapshots).
  // At first mount, frames is still empty (the source is loading) so surface
  // is empty; this effect runs again the moment frames arrive and the scene
  // is rebuilt with real data.
  useEffect(() => {
    if (surface.grid.length === 0) return; // wait for real data
    const mount = mountRef.current;
    if (!mount) return;
    const w = mount.clientWidth;
    const h = mount.clientHeight;

    // Scene, camera, renderer.
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    // Camera defaults tuned to match the classical vol-surface look (reference):
    //   - FOV 55° so the surface reads less top-down
    //   - Camera close + low so the surface fills most of the canvas
    const camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 100);
    camera.position.set(2.6, 1.3, 3.6);
    camera.lookAt(0, 0.45, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(w, h);
    mount.appendChild(renderer.domElement);

    // Orbit controls (mouse-drag rotate, right-drag pan, wheel zoom).
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 1.5;
    controls.maxDistance = 12;
    controls.target.set(0, 0.45, 0); // world-space center, matches camera.lookAt

    // --- Lighting ------------------------------------------------------------
    // Subtle ambient + two soft directional lights. The custom shader does
    // its own shading; lights are mostly for the helper meshes (axes/grid).
    scene.add(new THREE.AmbientLight(0xffffff, 0.45));
    const key = new THREE.DirectionalLight(0xffffff, 0.5);
    key.position.set(4, 6, 3);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.25);
    fill.position.set(-3, 2, -2);
    scene.add(fill);

    // --- World scales (declared early so axes & grid can reference them) ---
    const xs = surface.strikes; // log-moneyness k
    const ts = surface.minutes; // 0..389
    const tMax = ts[ts.length - 1] || 1;
    const ivRange = Math.max(1e-6, ivMax - ivMin);
    const kMax = Math.max(...xs.map(Math.abs));

    // World scales — chosen so the surface fills the axes box [-1..+1, 0..1, -1..+1].
    const xScale = kMax > 0 ? 1 / kMax : 32; // strike: world x ∈ [-1, +1]
    const tScale = 2.0; // minutes: world z ∈ [-1, +1] (centered)
    const yScale = 1.0; // IV: visible rise (clipped/capped at ivMax)
    const yOffset = 0.05;

    // --- Axes (X = strike, Y = IV, Z = time-into-session) -----------------
    // All three axes meet at the BACK-LEFT corner of the floor box so the lines
    // never cross the surface in the middle of the camera view:
    //   - K axis: front edge of the floor (z = +1, y = yOffset)
    //   - σ axis: back-left vertical edge (x = -1, z = -1), pointing up
    //   - t axis: left edge of the floor (x = -1, y = yOffset)
    // The anchor at (-1, yOffset, -1) is the back-left floor corner.
    const axes = new THREE.Group();
    const mkAxis = (
      from: THREE.Vector3,
      to: THREE.Vector3,
      color: number,
      label: string,
      labelPos: THREE.Vector3,
    ) => {
      const mat = new THREE.LineBasicMaterial({ color });
      const geom = new THREE.BufferGeometry().setFromPoints([from, to]);
      axes.add(new THREE.Line(geom, mat));
      // Label sprite.
      const c = document.createElement("canvas");
      c.width = 256;
      c.height = 64;
      const ctx = c.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#8E8E88";
        ctx.font = "32px ui-monospace, monospace";
        ctx.fillText(label, 4, 40);
      }
      const tex = new THREE.CanvasTexture(c);
      tex.minFilter = THREE.LinearFilter;
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: tex, transparent: true }),
      );
      sprite.position.copy(labelPos);
      sprite.scale.set(0.6, 0.15, 1);
      axes.add(sprite);
    };
    const corner = new THREE.Vector3(-1, yOffset, -1);
    mkAxis(
      new THREE.Vector3(-1, yOffset, +1),
      new THREE.Vector3(+1, yOffset, +1),
      0x0fb5a8,
      "K (log-moneyness)",
      new THREE.Vector3(+1.05, yOffset, +1),
    );
    mkAxis(
      corner.clone(),
      new THREE.Vector3(-1, yOffset + yScale, -1),
      0xb5002e,
      "\u03c3 (IV)",
      new THREE.Vector3(-1, yOffset + yScale + 0.05, -1),
    );
    mkAxis(
      corner.clone(),
      new THREE.Vector3(-1, yOffset, +1),
      0xfafaf7,
      "t (minutes)",
      new THREE.Vector3(-1, yOffset, +1.05),
    );
    scene.add(axes);

    // --- Grid (the floor at y=0) -------------------------------------------
    const grid = new THREE.GridHelper(2.4, 12, 0x8E8E88, 0x161618);
    grid.position.y = -0.001;
    grid.material.opacity = 0.4;
    grid.material.transparent = true;
    scene.add(grid);

    // --- The IV surface mesh -------------------------------------------------
    // World coordinates:
    //   X = strike (log-moneyness k; surface spans k ≈ ±0.03 mapped to world X ∈ [-1, +1])
    //   Y = IV (scaled to visible range [yOffset, yOffset + yScale])
    //   Z = minutes into session (0..tMax, mapped to world Z ∈ [-1, +1])
    const nx = xs.length;
    const nz = ts.length;
    const positions = new Float32Array(nx * nz * 3);
    const colors = new Float32Array(nx * nz * 3);
    const indices: number[] = [];

    for (let iz = 0; iz < nz; iz++) {
      for (let ix = 0; ix < nx; ix++) {
        const iv = surface.grid[iz][ix];
        const x = xs[ix] * xScale; // log-moneyness ≈ ±0.03 → world x ∈ [-1, +1]
        const z = (ts[iz] / tMax - 0.5) * tScale;
        // Clamp t to [0, 1] so late-session outliers above the 95th percentile
        // are capped at yScale (no runaway spike, stable color ramp).
        const t = iv == null ? 0 : Math.max(0, Math.min(1, (iv - ivMin) / ivRange));
        const y = iv == null ? yOffset : yOffset + t * yScale;
        const idx = (iz * nx + ix) * 3;
        positions[idx] = x;
        positions[idx + 1] = y;
        positions[idx + 2] = z;
        // Color ramp: low → turquoise, mid → bone, high → crimson.
        let r: number, g: number, b: number;
        if (iv == null) {
          r = g = b = 60;
        } else {
          if (t < 0.5) {
            const s = t * 2;
            r = 15 + (250 - 15) * s;
            g = 181 + (250 - 181) * s;
            b = 168 + (247 - 168) * s;
          } else {
            const s = (t - 0.5) * 2;
            r = 250 + (181 - 250) * s;
            g = 250 + (0 - 250) * s;
            b = 247 + (46 - 247) * s;
          }
        }
        colors[idx] = r / 255;
        colors[idx + 1] = g / 255;
        colors[idx + 2] = b / 255;
      }
    }

    // Build quad indices. Skip quads where any corner is null (iv missing).
    const v = (ix: number, iz: number) => iz * nx + ix;
    for (let iz = 0; iz < nz - 1; iz++) {
      for (let ix = 0; ix < nx - 1; ix++) {
        const a = surface.grid[iz][ix];
        const b = surface.grid[iz][ix + 1];
        const c = surface.grid[iz + 1][ix];
        const d = surface.grid[iz + 1][ix + 1];
        if (a == null || b == null || c == null || d == null) continue;
        indices.push(v(ix, iz), v(ix + 1, iz), v(ix + 1, iz + 1));
        indices.push(v(ix, iz), v(ix + 1, iz + 1), v(ix, iz + 1));
      }
    }

    const surfGeom = new THREE.BufferGeometry();
    surfGeom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    surfGeom.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    surfGeom.setIndex(indices);
    surfGeom.computeVertexNormals();

    // Custom ShaderMaterial: vertex colors + simple diffuse (half-Lambert) +
    // a Fresnel-ish rim so the surface reads as a volume even without textures.
    const surfMat = new THREE.ShaderMaterial({
      vertexColors: true,
      uniforms: {
        uLightDir: { value: new THREE.Vector3(0.6, 1.0, 0.4).normalize() },
        uRim: { value: 0.35 },
      },
      vertexShader: `
        varying vec3 vColor;
        varying vec3 vNormal;
        varying vec3 vViewDir;
        void main() {
          vColor = color;
          vNormal = normalize(normalMatrix * normal);
          vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
          vViewDir = normalize(-mvPos.xyz);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        varying vec3 vNormal;
        varying vec3 vViewDir;
        uniform vec3 uLightDir;
        uniform float uRim;
        void main() {
          // Half-Lambert diffuse (softer, less harsh terminator).
          float diff = clamp(dot(vNormal, normalize(uLightDir)) * 0.5 + 0.5, 0.0, 1.0);
          // Fresnel-ish rim brightens silhouette edges.
          float rim = pow(1.0 - max(dot(vNormal, vViewDir), 0.0), 2.5) * uRim;
          vec3 lit = vColor * (0.35 + 0.85 * diff) + rim * vec3(0.65, 0.65, 0.7);
          gl_FragColor = vec4(lit, 0.95);
        }
      `,
      side: THREE.DoubleSide,
      transparent: true,
    });

    const surfMesh = new THREE.Mesh(surfGeom, surfMat);
    scene.add(surfMesh);

    // --- "Now" cursor: a thin vertical crimson curtain at the playhead minute.
    // Narrow strip (0.04 wide) spanning the full surface height so it cuts the
    // relief like a cross-section, marking exactly where in time we are without
    // covering the surface like the previous floating plane did. Stays oriented
    // along Z (the time axis) — does NOT lookAt the camera.
    const cursorGeom = new THREE.PlaneGeometry(0.04, yScale + yOffset + 0.05);
    const cursorMat = new THREE.MeshBasicMaterial({
      color: 0xb5002e,
      transparent: true,
      opacity: 0.55,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const cursorMesh = new THREE.Mesh(cursorGeom, cursorMat);
    cursorMesh.position.set(
      0,
      (yScale + yOffset) * 0.5, // centered vertically across the IV range
      (initialPlayhead / tMax - 0.5) * tScale,
    );
    scene.add(cursorMesh);
    cursorMeshRef.current = cursorMesh;

    // Two thin vertical crimson lines on either side of the curtain = high-
    // contrast outline so the cursor reads cleanly against bright surface pixels.
    // Attached as children of the cursor mesh so they inherit its position
    // (the playhead sync effect then needs no extra logic).
    const cursorEdgeGeom = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, yOffset - 0.01, 0),
      new THREE.Vector3(0, yOffset + yScale + 0.05, 0),
    ]);
    const cursorEdgeMat = new THREE.LineBasicMaterial({ color: 0xb5002e });
    const cursorLeftEdge = new THREE.Line(cursorEdgeGeom, cursorEdgeMat);
    cursorLeftEdge.position.x = -0.02;
    const cursorRightEdge = new THREE.Line(cursorEdgeGeom, cursorEdgeMat);
    cursorRightEdge.position.x = +0.02;
    cursorMesh.add(cursorLeftEdge);
    cursorMesh.add(cursorRightEdge);

    // --- Resize handling ----------------------------------------------------
    const onResize = () => {
      const w2 = mount.clientWidth;
      const h2 = mount.clientHeight;
      camera.aspect = w2 / h2;
      camera.updateProjectionMatrix();
      renderer.setSize(w2, h2);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    // --- Render loop ---------------------------------------------------------
    let raf = 0;
    let stopped = false;
    const tick = () => {
      if (stopped) return;
      controls.update();
      // The playhead curtain stays perpendicular to the time axis (Z) — no
      // lookAt(camera); its purpose is to mark time, not face the viewer.
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      surfGeom.dispose();
      surfMat.dispose();
      cursorGeom.dispose();
      cursorMat.dispose();
      cursorEdgeGeom.dispose();
      cursorEdgeMat.dispose();
      axes.traverse((o) => {
        const m = o as THREE.Line;
        if (m.geometry) m.geometry.dispose();
        if ((m.material as THREE.Material)?.dispose) (m.material as THREE.Material).dispose();
      });
      grid.geometry.dispose();
      (grid.material as THREE.Material).dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
      cursorMeshRef.current = null;
    };
    // We intentionally exclude `playheadMinute` from deps: the scene is
    // rebuilt whenever `surface` changes (frames arrive or SVI re-fits).
    // The playhead position is synced via a separate effect below (live
    // updates only, no full rebuild).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [surface, ivMin, ivMax]);

  // Update playhead cursor position when the playhead changes (cheap live update).
  // The two edge lines are children of the cursor mesh, so they follow it.
  useEffect(() => {
    const cursor = cursorMeshRef.current;
    if (!cursor || surface.minutes.length === 0) return;
    const tMax = surface.minutes[surface.minutes.length - 1] || 1;
    const tScale = 2.0;
    cursor.position.z = (playheadMinute / tMax - 0.5) * tScale;
    cursor.visible = playheadMinute >= 0 && playheadMinute <= tMax;
  }, [playheadMinute, surface]);

  return (
    <div className={`relative min-w-0 ${className}`}>
      <div
        ref={mountRef}
        className="relative min-h-[560px] flex-1 overflow-hidden rounded-[4px] border border-rule/40 bg-black"
      />
    </div>
  );
}
