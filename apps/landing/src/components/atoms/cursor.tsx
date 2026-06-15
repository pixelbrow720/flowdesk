"use client";

import { useEffect, useState } from "react";
import { motion, useMotionValue, useSpring, AnimatePresence } from "motion/react";

/**
 * Custom cursor — tiny dot + crimson trailing ring.
 * Inflates on hover over [data-cursor="grow"].
 */
export function Cursor() {
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const ringX = useSpring(x, { stiffness: 200, damping: 24, mass: 0.6 });
  const ringY = useSpring(y, { stiffness: 200, damping: 24, mass: 0.6 });
  const [variant, setVariant] = useState<"default" | "grow" | "hidden">("default");
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(pointer: coarse)").matches) return;
    setEnabled(true);

    const move = (e: PointerEvent) => {
      x.set(e.clientX);
      y.set(e.clientY);
    };
    const over = (e: PointerEvent) => {
      const t = e.target as HTMLElement | null;
      if (!t) return;
      const grow = t.closest('[data-cursor="grow"]');
      const hide = t.closest('[data-cursor="hide"]');
      setVariant(hide ? "hidden" : grow ? "grow" : "default");
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerover", over);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerover", over);
    };
  }, [x, y]);

  if (!enabled) return null;

  return (
    <>
      {/* dot */}
      <motion.div
        className="pointer-events-none fixed left-0 top-0 z-[100] h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brick"
        style={{ x, y }}
      />
      {/* ring */}
      <AnimatePresence>
        {variant !== "hidden" && (
          <motion.div
            initial={false}
            animate={{
              width: variant === "grow" ? 64 : 28,
              height: variant === "grow" ? 64 : 28,
              opacity: variant === "grow" ? 1 : 0.55,
              borderColor: variant === "grow" ? "rgba(184,51,62,0.9)" : "rgba(250,250,247,0.35)",
            }}
            transition={{ type: "spring", stiffness: 280, damping: 24 }}
            className="pointer-events-none fixed left-0 top-0 z-[99] -translate-x-1/2 -translate-y-1/2 rounded-full border"
            style={{ x: ringX, y: ringY }}
          />
        )}
      </AnimatePresence>
    </>
  );
}
