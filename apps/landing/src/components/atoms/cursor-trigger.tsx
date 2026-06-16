"use client";

/**
 * CursorTrigger — ASCII smoke that follows the cursor.
 *
 * Concept:
 *   On mousemove we measure cursor speed (px/ms, EMA-smoothed) and spawn
 *   particles whose count scales linearly with that speed:
 *     - cursor still              → 0 particles (silence)
 *     - cursor drifting           → 1-2 particles/tick (thin wisp)
 *     - cursor moving fast        → up to 8 particles/tick (thick smoke)
 *   When mousemove stops firing, the speed value decays ~95%/frame so
 *   trailing wisps thin out within ~300ms of idle, then stop entirely.
 *
 *   Each particle is a single ASCII glyph with:
 *     - position (x, y) seeded near the cursor with jitter
 *     - velocity = (cursor velocity * inherit factor) + upward rise + drift
 *     - age that grows each frame; opacity fades from full → 0 over lifeMs
 *     - glyph picked from a density ramp tied to age:
 *         fresh particle = denser glyph (▓ ▒ # *)
 *         middle-aged    = mid-density (░ ~ ^ `)
 *         dying          = sparse (. , ' )
 *   When age >= lifeMs the particle is culled.
 *
 * Why canvas, not DOM:
 *   Hundreds of glyphs in flight; DOM nodes would thrash layout. A single
 *   <canvas> with `mix-blend-mode: screen` lets the brick smoke read as
 *   additive light over the page's pure-black sections.
 *
 * Disabled on:
 *   - touch-primary devices (no hover)
 *   - prefers-reduced-motion
 *
 * NOT a custom cursor. Native system cursor stays. The canvas sits
 * pointer-events: none and mounts above all section content (z-[60]).
 */

import { useEffect, useRef } from "react";

// Density ramp — fresh particles use denser glyphs, dying ones use sparse.
// Order matters: index 0 = densest (just-spawned), last = sparsest (about to die).
// Chose chars that read distinctly at 16-18px in JetBrains Mono:
//   ▓ ▒ ░  = shading blocks (most "smoke body")
//   # *    = dense punctuation (chunky)
//   ~ ^ ` = thin wisps
//   . , ' = trailing dissipation
const GLYPHS = ["▓", "▒", "▒", "░", "░", "#", "*", "~", "^", "`", ".", ",", "'", " "];

// Tuning knobs (kept as constants, not props — landing page is a fixed surface).
const SPAWN_RATE_MS = 14; // min ms between spawn ticks (~70/sec at peak)
// Velocity-driven spawn density.
//   - Stationary cursor: NO spawn. Smoke only appears when you move.
//   - Slow drift: 1-2 particles/tick (thin wisp).
//   - Fast slash: up to 8 particles/tick (thick smoke trail).
// Speed measured in px/ms between consecutive mousemove events.
const SPEED_MIN = 0.05; // below this = cursor essentially still, skip spawn
const SPEED_FOR_FULL_DENSITY = 1.8; // px/ms, ~108 px/frame@60fps
const PARTICLES_MIN = 1;
const PARTICLES_MAX = 8;
const SPEED_SMOOTHING = 0.18; // EMA factor; 0 = freeze, 1 = no smoothing
const LIFE_MIN_MS = 900;
const LIFE_MAX_MS = 1700;
const FONT_SIZE_BASE = 16;
const FONT_SIZE_JITTER = 4; // ±px so smoke has varied weight
const SPAWN_JITTER_PX = 22; // initial position jitter around cursor
const VX_JITTER = 0.45; // horizontal drift (px/frame at 60fps)
const VY_RISE = -0.55; // vertical rise (negative = up)
const VY_JITTER = 0.3;
const VX_DAMP = 0.985; // per-frame damping so trail spreads then settles
// How much cursor velocity is inherited by spawned particles. Faster
// cursor → particles fly further along the motion vector before rising.
const VELOCITY_INHERIT = 0.12;

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number; // ms
  life: number; // ms
  size: number; // px font size for this glyph
}

export function CursorTrigger() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (typeof window === "undefined") return;

    // Bail on no-hover devices and reduced motion.
    const isTouch = window.matchMedia?.("(hover: none)").matches;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (isTouch || reduced) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const resize = () => {
      dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // baseline font config; per-particle draw will reset font size dynamically
      ctx.font = `${FONT_SIZE_BASE}px var(--font-mono, "JetBrains Mono", ui-monospace, monospace)`;
      ctx.textBaseline = "middle";
      ctx.textAlign = "center";
    };
    resize();

    const particles: Particle[] = [];
    let cursorX = -9999;
    let cursorY = -9999;
    let lastMoveX = -9999;
    let lastMoveY = -9999;
    let lastMoveTime = 0;
    // Smoothed cursor speed in px/ms. Decays toward 0 when no movement.
    let speed = 0;
    // Cursor velocity vector (px/ms), used so particles inherit motion direction.
    let velX = 0;
    let velY = 0;
    let lastSpawn = 0;
    let cursorActive = false;

    const spawn = (now: number) => {
      if (now - lastSpawn < SPAWN_RATE_MS) return;
      // Below minimum speed → cursor is effectively stationary. No spawn.
      // This is the "smoke only on movement" rule the design calls for.
      if (speed < SPEED_MIN) return;
      lastSpawn = now;
      // Map speed → particle count. Linear ramp clamped to [MIN, MAX].
      const t = Math.min(1, (speed - SPEED_MIN) / (SPEED_FOR_FULL_DENSITY - SPEED_MIN));
      const count = Math.max(
        PARTICLES_MIN,
        Math.round(PARTICLES_MIN + (PARTICLES_MAX - PARTICLES_MIN) * t)
      );
      for (let i = 0; i < count; i++) {
        particles.push({
          x: cursorX + (Math.random() - 0.5) * SPAWN_JITTER_PX,
          y: cursorY + (Math.random() - 0.5) * SPAWN_JITTER_PX * 0.6,
          // Inherit a fraction of cursor velocity so the trail follows the
          // motion vector, then add the usual random drift + upward rise.
          vx: velX * VELOCITY_INHERIT + (Math.random() - 0.5) * VX_JITTER * 2,
          vy:
            velY * VELOCITY_INHERIT +
            VY_RISE +
            (Math.random() - 0.5) * VY_JITTER * 2,
          age: 0,
          life: LIFE_MIN_MS + Math.random() * (LIFE_MAX_MS - LIFE_MIN_MS),
          size: FONT_SIZE_BASE + (Math.random() - 0.5) * FONT_SIZE_JITTER * 2,
        });
      }
    };

    const onMove = (e: MouseEvent) => {
      const now = performance.now();
      // First-ever move: just seed position, no velocity yet.
      if (lastMoveX < 0) {
        lastMoveX = e.clientX;
        lastMoveY = e.clientY;
        lastMoveTime = now;
      }
      const dt = Math.max(1, now - lastMoveTime); // ms, guard against /0
      const dx = e.clientX - lastMoveX;
      const dy = e.clientY - lastMoveY;
      const instantSpeed = Math.hypot(dx, dy) / dt; // px/ms
      // EMA smoothing so a single jittery sample doesn't dominate.
      speed = speed * (1 - SPEED_SMOOTHING) + instantSpeed * SPEED_SMOOTHING;
      // Velocity vector smoothed the same way.
      velX = velX * (1 - SPEED_SMOOTHING) + (dx / dt) * SPEED_SMOOTHING;
      velY = velY * (1 - SPEED_SMOOTHING) + (dy / dt) * SPEED_SMOOTHING;
      cursorX = e.clientX;
      cursorY = e.clientY;
      lastMoveX = e.clientX;
      lastMoveY = e.clientY;
      lastMoveTime = now;
      cursorActive = true;
    };
    const onLeave = () => {
      cursorActive = false;
    };
    const onEnter = () => {
      cursorActive = true;
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    document.addEventListener("mouseleave", onLeave);
    document.addEventListener("mouseenter", onEnter);
    window.addEventListener("resize", resize);

    let raf = 0;
    let prev = performance.now();

    const tick = (now: number) => {
      const dtMs = Math.min(48, now - prev); // cap to avoid teleport on tab refocus
      prev = now;

      // Decay speed every frame. If cursor stops moving, mousemove stops
      // firing — without decay, `speed` would stay frozen at the last
      // measured value and we'd keep spawning. Multiplicative decay falls
      // off cleanly (~95%/frame so wisps thin out within ~300ms of idle).
      const decay = Math.pow(0.95, dtMs / 16.6667);
      speed *= decay;
      velX *= decay;
      velY *= decay;

      if (cursorActive) spawn(now);

      // Clear with full transparency. Trails are produced by particle lifetime,
      // not by leftover canvas content — keeps the blend mode predictable.
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Update + draw.
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.age += dtMs;
        if (p.age >= p.life) {
          particles.splice(i, 1);
          continue;
        }
        // Frame-rate normalised step (60fps reference).
        const step = dtMs / 16.6667;
        p.x += p.vx * step;
        p.y += p.vy * step;
        p.vx *= VX_DAMP;
        // Gentle horizontal wander so smoke breathes.
        p.vx += (Math.random() - 0.5) * 0.05 * step;

        const t = p.age / p.life; // 0 = fresh, 1 = dying
        // Opacity: ramp up fast (inhale), then fade out (exhale).
        const fadeIn = Math.min(1, p.age / 80);
        const fadeOut = 1 - t;
        const alpha = Math.max(0, fadeIn * fadeOut * 0.85);

        // Glyph index from density ramp — earlier ages = denser glyphs.
        const gi = Math.min(GLYPHS.length - 1, Math.floor(t * GLYPHS.length));
        const glyph = GLYPHS[gi];
        if (glyph === " ") continue; // no point drawing whitespace

        ctx.fillStyle = `rgba(224, 24, 60, ${alpha.toFixed(3)})`;
        ctx.font = `${p.size.toFixed(1)}px var(--font-mono, "JetBrains Mono", ui-monospace, monospace)`;
        ctx.fillText(glyph, p.x, p.y);
      }

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("mouseenter", onEnter);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      // z-[60] above section content + nav. mix-blend-screen so brick reads
      // as additive light over the bg-ink-0 sections (pure black absorbs
      // standard rgba; screen-blending makes the smoke "glow").
      className="pointer-events-none fixed inset-0 z-[60]"
      style={{ mixBlendMode: "screen" }}
    />
  );
}
