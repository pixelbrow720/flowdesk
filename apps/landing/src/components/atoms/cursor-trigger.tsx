"use client";

/**
 * CursorTrigger — soft brick "smoke" that follows the cursor.
 *
 * Implementation:
 *   - Fixed-position div, full viewport, pointer-events-none, z-0.
 *   - Renders a radial-gradient at (x, y) that updates on mousemove via CSS variables.
 *   - rAF-throttled to keep paint cheap (~60fps cap).
 *   - mix-blend-mode: screen — additive on black, looks like emissive smoke.
 *   - Idle/no-cursor (touch) → invisible.
 *
 * NOT a custom cursor. Native system cursor remains.
 */

import { useEffect, useRef } from "react";

export function CursorTrigger() {
  const layerRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef({ x: -9999, y: -9999, vis: 0, raf: 0 });

  useEffect(() => {
    const el = layerRef.current;
    if (!el) return;

    // Bail out on touch-primary devices — cursor trigger makes no sense there.
    const isTouch =
      typeof window !== "undefined" &&
      window.matchMedia?.("(hover: none)").matches;
    if (isTouch) return;

    const onMove = (e: MouseEvent) => {
      stateRef.current.x = e.clientX;
      stateRef.current.y = e.clientY;
      stateRef.current.vis = 1;
      schedule();
    };
    const onLeave = () => {
      stateRef.current.vis = 0;
      schedule();
    };

    let pending = false;
    const schedule = () => {
      if (pending) return;
      pending = true;
      stateRef.current.raf = requestAnimationFrame(() => {
        pending = false;
        const { x, y, vis } = stateRef.current;
        el.style.setProperty("--cx", `${x}px`);
        el.style.setProperty("--cy", `${y}px`);
        el.style.setProperty("--cv", String(vis));
      });
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mouseleave", onLeave);
    document.addEventListener("mouseleave", onLeave);

    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("mouseleave", onLeave);
      cancelAnimationFrame(stateRef.current.raf);
    };
  }, []);

  return (
    <div
      ref={layerRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 transition-opacity duration-300"
      style={{
        // Soft brick smoke — radial gradient centered on cursor.
        background:
          "radial-gradient(420px 420px at var(--cx, -9999px) var(--cy, -9999px), rgba(184,51,62,0.28), rgba(184,51,62,0.10) 30%, transparent 65%)",
        mixBlendMode: "screen",
        opacity: "var(--cv, 0)",
        // Subtle blur to soften the gradient into "smoke".
        filter: "blur(8px)",
      }}
    />
  );
}
