"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { SplitText } from "@/components/atoms/split-text";

/**
 * HERO — operator-grade opening.
 * - Big mask-rise headline ("Workspace. For operators.")
 * - Crimson rule-line that grows from 0 → full width
 * - Rotating verb chip ("decisions / signal / execution")
 * - Background grid that parallaxes up as you scroll
 * - Spec strip at bottom (FOG · FLUX · ARC · OUTPUT)
 */
export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });

  const gridY = useTransform(scrollYProgress, [0, 1], ["0%", "-30%"]);
  const headlineY = useTransform(scrollYProgress, [0, 1], ["0%", "-12%"]);
  const headlineOpacity = useTransform(scrollYProgress, [0, 0.7, 1], [1, 0.4, 0]);

  return (
    <section
      ref={ref}
      className="relative isolate flex min-h-screen flex-col justify-end overflow-hidden pb-12 pt-32 md:pb-20"
    >
      {/* parallax grid */}
      <motion.div
        style={{ y: gridY }}
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.18]"
        aria-hidden
      >
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgba(250,250,247,0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(250,250,247,0.08) 1px, transparent 1px)",
            backgroundSize: "72px 72px",
            maskImage: "radial-gradient(ellipse at 50% 60%, #000 30%, transparent 75%)",
          }}
        />
      </motion.div>

      {/* radial crimson glow */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 100%, rgba(230,57,70,0.25), transparent 70%)",
        }}
        aria-hidden
      />

      <div className="container-grid">
        {/* eyebrow row */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="mb-8 flex flex-wrap items-center gap-x-6 gap-y-2 md:mb-10"
        >
          <span className="eyebrow flex items-center gap-2">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal-green" />
            v0.4 — Paid Beta · Live
          </span>
          <span className="eyebrow text-bone-3">SOC2-grade · Single tenant</span>
        </motion.div>

        {/* headline */}
        <motion.h1
          style={{ y: headlineY, opacity: headlineOpacity }}
          className="text-display-1 text-balance"
        >
          <SplitText text="Workspace." by="word" />
          <br />
          <span className="text-crimson">
            <SplitText text="For operators." by="word" delay={0.15} />
          </span>
        </motion.h1>

        {/* crimson rule */}
        <motion.div
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 1.4, delay: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="my-10 h-[2px] w-full origin-left bg-crimson md:my-14"
        />

        {/* sub-grid: lede + meta */}
        <div className="grid grid-cols-12 gap-6 md:gap-10">
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.7, ease: [0.16, 1, 0.3, 1] }}
            className="col-span-12 max-w-[42ch] text-balance text-lg leading-snug text-bone-1 md:col-span-6 md:text-2xl"
          >
            Decisions, execution, and signal — without the bloat. FlowDesk pairs a context engine
            with deterministic automation so your team ships, not searches.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.85, ease: [0.16, 1, 0.3, 1] }}
            className="col-span-12 flex flex-col gap-4 md:col-span-6 md:items-end md:text-right"
          >
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
              Stack — FOG · FLUX · ARC
            </div>
            <div className="flex flex-wrap items-center gap-3 md:justify-end">
              <a
                href="#cta"
                data-cursor="grow"
                className="group relative inline-flex h-12 items-center gap-3 overflow-hidden rounded-full bg-crimson px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-bone-0 transition-transform hover:scale-[1.02]"
              >
                <span className="relative z-10">Request access</span>
                <span className="relative z-10">→</span>
                <span className="absolute inset-0 bg-crimson-deep opacity-0 transition-opacity group-hover:opacity-100" />
              </a>
              <a
                href="#system"
                data-cursor="grow"
                className="inline-flex h-12 items-center gap-3 rounded-full border border-[color:var(--hairline-strong)] px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-bone-1 transition-colors hover:border-bone-2 hover:text-bone-0"
              >
                See the system <span className="text-crimson">↓</span>
              </a>
            </div>
          </motion.div>
        </div>

        {/* spec strip */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1, ease: [0.16, 1, 0.3, 1] }}
          className="mt-16 grid grid-cols-2 gap-px overflow-hidden rounded border border-[color:var(--hairline)] bg-[color:var(--hairline)] md:mt-24 md:grid-cols-4"
        >
          {[
            ["FOG", "Context engine"],
            ["FLUX", "Deterministic automation"],
            ["ARC", "Multi-agent orchestration"],
            ["OUTPUT", "Operator dashboards"],
          ].map(([k, v]) => (
            <div key={k} className="bg-ink-0 p-5 md:p-6">
              <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-crimson">
                {k}
              </div>
              <div className="mt-2 text-base text-bone-1 md:text-lg">{v}</div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
