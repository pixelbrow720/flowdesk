"use client";

import { motion, useScroll, useMotionValueEvent } from "motion/react";
import { useState } from "react";
import clsx from "clsx";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, "change", (v) => setScrolled(v > 32));

  return (
    <motion.header
      initial={{ y: -40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
      className={clsx(
        "fixed inset-x-0 top-0 z-50 transition-[backdrop-filter,background-color,border-color] duration-500",
        scrolled
          ? "border-b border-[color:var(--hairline)] bg-ink-0/70 backdrop-blur-md"
          : "border-b border-transparent"
      )}
    >
      <div className="container-grid flex h-16 items-center justify-between md:h-20">
        <a href="#" className="flex items-center gap-2.5" data-cursor="grow">
          <Logo />
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-bone-2">
            FlowDesk
          </span>
        </a>
        <nav className="hidden items-center gap-8 md:flex">
          {["System", "Lenses", "Workflows", "Pricing"].map((l) => (
            <a
              key={l}
              href={`#${l.toLowerCase()}`}
              data-cursor="grow"
              className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-2 transition-colors hover:text-teal-glow"
            >
              {l}
            </a>
          ))}
        </nav>
        <a
          href="#cta"
          data-cursor="grow"
          className="group relative inline-flex h-10 items-center gap-2 overflow-hidden rounded-full border border-[color:var(--hairline-strong)] bg-ink-2/60 px-5 font-mono text-[11px] uppercase tracking-[0.18em] text-bone-0 transition-colors hover:border-brick"
        >
          <span className="relative z-10">Request access</span>
          <span className="relative z-10 text-brick transition-transform group-hover:translate-x-0.5">→</span>
          <span className="absolute inset-0 -z-0 translate-y-full bg-brick transition-transform duration-500 group-hover:translate-y-0" />
        </a>
      </div>
    </motion.header>
  );
}

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
      <rect x="1" y="1" width="20" height="20" rx="4" stroke="currentColor" strokeOpacity="0.4" />
      <rect x="6" y="6" width="10" height="10" rx="1" fill="#B8333E" />
    </svg>
  );
}
