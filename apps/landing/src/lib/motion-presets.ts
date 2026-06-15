/**
 * Motion choreography tokens.
 * Single source of truth for all easing/spring/duration across the site.
 */

import type { Transition } from "motion/react";

export const ease = {
  // CSS-style cubic — soft entrance
  out: [0.16, 1, 0.3, 1] as const,
  // Tighter, operator-grade
  outFast: [0.22, 1, 0.36, 1] as const,
  inOut: [0.65, 0, 0.35, 1] as const,
};

export const spring = {
  // FlowDesk default — calm but immediate
  base: { type: "spring", stiffness: 200, damping: 28, mass: 1 } satisfies Transition,
  // Pin/scrub — heavier, holds shapes
  pin: { type: "spring", stiffness: 120, damping: 30, mass: 1.1 } satisfies Transition,
  // Card hover / micro
  micro: { type: "spring", stiffness: 380, damping: 26, mass: 0.6 } satisfies Transition,
};

export const duration = {
  fast: 0.32,
  base: 0.6,
  slow: 0.9,
  reveal: 1.1,
};

/** Stagger choreography — for split-text and list reveals */
export const stagger = {
  word: 0.04,
  line: 0.08,
  card: 0.06,
};

/** Standard fade+rise from below */
export const fadeRise = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "0px 0px -10% 0px" },
  transition: { duration: duration.reveal, ease: ease.out },
};

/** Mask reveal — clip-path inset wipe (Circle-style) */
export const maskRise = {
  initial: { clipPath: "inset(100% 0% 0% 0%)" },
  whileInView: { clipPath: "inset(0% 0% 0% 0%)" },
  viewport: { once: true, margin: "0px 0px -15% 0px" },
  transition: { duration: 1.2, ease: ease.out },
};
