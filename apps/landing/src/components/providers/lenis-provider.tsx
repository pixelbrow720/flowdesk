"use client";

import { useEffect, useRef } from "react";
import Lenis from "lenis";

/**
 * Lenis v1.1.x smooth scroll provider.
 * - Tuned to match FlowDesk operator feel (slightly snappier than default Circle).
 * - Disables on prefers-reduced-motion.
 * - Exposes window.__lenis for Motion's useScroll() integration.
 */
export function LenisProvider({ children }: { children: React.ReactNode }) {
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const lenis = new Lenis({
      duration: 1.05,
      // exponential ease — feels weighty without being syrupy
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: "vertical",
      gestureOrientation: "vertical",
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 1.4,
      infinite: false,
    });

    // expose for Motion's useScroll integration
    (window as unknown as { __lenis?: Lenis }).__lenis = lenis;

    function raf(time: number) {
      lenis.raf(time);
      rafRef.current = requestAnimationFrame(raf);
    }
    rafRef.current = requestAnimationFrame(raf);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lenis.destroy();
      delete (window as unknown as { __lenis?: Lenis }).__lenis;
    };
  }, []);

  return <>{children}</>;
}
