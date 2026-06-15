"use client";

import { motion } from "motion/react";

/**
 * MARQUEE — infinite horizontal tape.
 * Pure CSS keyframe animation; we duplicate content so the loop is seamless.
 * Pauses on hover.
 */
export function Marquee() {
  return (
    <section className="relative overflow-hidden border-y border-[color:var(--hairline)] bg-ink-1 py-10 md:py-14">
      <div className="container-grid mb-8 flex items-baseline justify-between">
        <span className="eyebrow">[04] In production</span>
        <span className="eyebrow text-bone-3">Operator teams · 2024–2025</span>
      </div>

      {/* tape */}
      <div className="group relative flex overflow-hidden">
        <motion.div
          className="flex shrink-0 items-center gap-12 pr-12 will-change-transform group-hover:[animation-play-state:paused] animate-marquee"
          aria-hidden={false}
        >
          {ITEMS.concat(ITEMS).map((item, i) => (
            <Pill key={`${item}-${i}`} label={item} />
          ))}
        </motion.div>
      </div>

      {/* secondary tape — opposite direction, slower, smaller, teal accent */}
      <div className="group relative mt-6 flex overflow-hidden opacity-70">
        <motion.div
          className="flex shrink-0 items-center gap-10 pr-10 will-change-transform group-hover:[animation-play-state:paused]"
          style={{ animation: "marquee 60s linear infinite reverse" }}
        >
          {STATS.concat(STATS).map((s, i) => (
            <span key={`${s}-${i}`} className="font-mono text-[11px] uppercase tracking-[0.18em] text-teal-glow whitespace-nowrap">
              {s}
            </span>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

function Pill({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 whitespace-nowrap">
      <span className="h-1.5 w-1.5 rounded-full bg-brick" />
      <span className="text-2xl font-medium text-bone-1 md:text-3xl">{label}</span>
    </div>
  );
}

const ITEMS = [
  "Decisions logged",
  "Workflows replayed",
  "Signals fired",
  "Agents scoped",
  "Context recalled",
  "Throughput tracked",
];

const STATS = [
  "P95 — 78ms",
  "FOG recall — 184ms",
  "FLUX runs — 12.4k/wk",
  "ARC agents — bounded · 6",
  "Single-tenant · BYOK",
  "Replay — 100%",
];
