"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";

/**
 * SYSTEM — visual stack diagram with scroll-driven assembly.
 * As you scroll, layers stack from bottom to top: FOG → FLUX → ARC → OUTPUT.
 */
export function System() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.7", "end 0.3"] });

  return (
    <section id="system" ref={ref} className="relative border-t border-[color:var(--hairline)] py-32 md:py-44">
      <div className="container-grid">
        <div className="mb-16 grid grid-cols-12 gap-6 md:mb-24">
          <div className="col-span-12 md:col-span-5">
            <span className="eyebrow">[03] System</span>
            <h2 className="mt-6 text-balance text-4xl font-medium leading-[1.05] md:text-6xl">
              Four layers. <span className="text-brick">One graph.</span>
            </h2>
          </div>
          <p className="col-span-12 max-w-[48ch] text-lg text-bone-2 md:col-span-6 md:col-start-7 md:text-xl">
            Not a feature list — an architecture. Each layer plugs into the next without leaks. You
            replace none of them; together, they replace everything else.
          </p>
        </div>

        {/* stack */}
        <div className="grid grid-cols-12 gap-10">
          <div className="col-span-12 lg:col-span-7">
            <div className="space-y-3">
              {LAYERS.map((layer, i) => (
                <Layer key={layer.id} layer={layer} progress={scrollYProgress} index={i} total={LAYERS.length} />
              ))}
            </div>
          </div>

          {/* sidebar specs */}
          <div className="col-span-12 lg:col-span-5">
            <div className="sticky top-28 space-y-4">
              {LAYERS.map((l, i) => (
                <div
                  key={l.id}
                  className={`border-l-2 pl-4 ${
                    i % 2 === 0 ? "border-brick/50" : "border-teal/60"
                  }`}
                >
                  <div
                    className={`font-mono text-[11px] uppercase tracking-[0.18em] ${
                      i % 2 === 0 ? "text-brick" : "text-teal-glow"
                    }`}
                  >
                    {l.id}
                  </div>
                  <div className="mt-1 text-base text-bone-1">{l.tagline}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Layer({
  layer,
  progress,
  index,
  total,
}: {
  layer: (typeof LAYERS)[number];
  progress: import("motion/react").MotionValue<number>;
  index: number;
  total: number;
}) {
  // each layer reveals on its slice
  const start = index / total;
  const end = (index + 1) / total;
  const opacity = useTransform(progress, [start, end], [0.25, 1]);
  const x = useTransform(progress, [start, end], [-40, 0]);

  return (
    <motion.div
      style={{ opacity, x }}
      className="group relative overflow-hidden rounded-lg border border-[color:var(--hairline-strong)] bg-ink-1 p-6 transition-colors hover:border-brick/40 md:p-8"
    >
      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-4">
          <span
            className={`font-mono text-[11px] ${
              index % 2 === 0 ? "text-brick" : "text-teal-glow"
            }`}
          >
            L{index + 1}
          </span>
          <h3 className="text-2xl font-medium md:text-3xl">{layer.id}</h3>
        </div>
        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
          {layer.kind}
        </span>
      </div>
      <p className="mt-3 max-w-[60ch] text-bone-2 md:text-lg">{layer.copy}</p>
      <div className="mt-6 flex flex-wrap gap-2">
        {layer.tags.map((t) => (
          <span
            key={t}
            className="inline-flex items-center rounded-full border border-[color:var(--hairline)] bg-ink-2 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-bone-2"
          >
            {t}
          </span>
        ))}
      </div>
      {/* accent on hover */}
      <div
        className={`absolute inset-x-0 bottom-0 h-px origin-left scale-x-0 transition-transform duration-700 group-hover:scale-x-100 ${
          index % 2 === 0 ? "bg-brick" : "bg-teal"
        }`}
      />
    </motion.div>
  );
}

const LAYERS = [
  {
    id: "FOG",
    kind: "Context Engine",
    tagline: "Memory + retrieval",
    copy: "Indexes everything: docs, code, decisions, threads. Vector + graph. Sub-200ms recall. Every prompt arrives loaded.",
    tags: ["Vector", "Graph", "BYOK", "<200ms"],
  },
  {
    id: "FLUX",
    kind: "Automation",
    tagline: "Typed workflows",
    copy: "Deterministic graph runtime. Typed inputs/outputs, versioned, replayable. Side-effects logged.",
    tags: ["DAG", "Typed", "Versioned", "Replay"],
  },
  {
    id: "ARC",
    kind: "Orchestration",
    tagline: "Multi-agent",
    copy: "Bounded concurrency, scoped agents, sandboxed tools. Each agent inherits FOG, runs FLUX, reports to OUTPUT.",
    tags: ["Multi-agent", "Bounded", "Sandboxed"],
  },
  {
    id: "OUTPUT",
    kind: "Surfaces",
    tagline: "Operator UI",
    copy: "Dashboards, decision logs, signal lenses. Keyboard-first. Sub-80ms p95. Built for instruments, not toys.",
    tags: ["Dashboard", "⌘K", "Real-time"],
  },
];
