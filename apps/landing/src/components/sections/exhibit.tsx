"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";

/**
 * EXHIBIT — scroll-driven bar chart "before/after FlowDesk."
 * Bars grow as the section enters viewport, anchored to scroll progress.
 */
export function Exhibit() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.8", "end 0.4"] });

  return (
    <section ref={ref} className="relative border-t border-[color:var(--hairline)] py-32 md:py-44">
      <div className="container-grid">
        <div className="mb-16 flex items-baseline justify-between md:mb-24">
          <span className="eyebrow">[05] Exhibit A</span>
          <span className="eyebrow text-bone-3">Operator team · 12 wk</span>
        </div>

        <div className="grid grid-cols-12 gap-10">
          <div className="col-span-12 lg:col-span-5">
            <h2 className="text-balance text-4xl font-medium leading-[1.05] md:text-5xl">
              The shape of work, <span className="text-crimson">before & after.</span>
            </h2>
            <p className="mt-6 max-w-[44ch] text-bone-2 md:text-lg">
              Same team, same headcount, same comp plan. Twelve weeks on FlowDesk. Searching collapses,
              shipping climbs, decisions become traceable.
            </p>
          </div>

          <div className="col-span-12 lg:col-span-7">
            <div className="space-y-7">
              {METRICS.map((m, i) => (
                <Bar key={m.label} metric={m} progress={scrollYProgress} index={i} />
              ))}
            </div>
            <div className="mt-10 flex items-baseline justify-between border-t border-[color:var(--hairline)] pt-4">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
                Source — internal pilot, n=14 teams
              </span>
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
                v0.4
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Bar({
  metric,
  progress,
  index,
}: {
  metric: (typeof METRICS)[number];
  progress: import("motion/react").MotionValue<number>;
  index: number;
}) {
  // each bar reveals over its slice of the scroll
  const start = Math.max(0, index * 0.12);
  const end = Math.min(1, start + 0.5);
  const width = useTransform(progress, [start, end], ["0%", `${metric.after}%`]);
  const baselineWidth = useTransform(progress, [start, end], ["0%", `${metric.before}%`]);

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-2">
          {metric.label}
        </span>
        <span className="font-mono text-[11px] text-bone-3">
          {metric.beforeLabel} → <span className="text-crimson">{metric.afterLabel}</span>
        </span>
      </div>
      {/* baseline (before) */}
      <div className="relative h-6 w-full overflow-hidden rounded-sm border border-[color:var(--hairline)] bg-ink-1">
        <motion.div
          style={{ width: baselineWidth }}
          className="absolute inset-y-0 left-0 bg-bone-3/30"
        />
        <motion.div
          style={{ width }}
          className="absolute inset-y-0 left-0 bg-crimson"
        />
      </div>
    </div>
  );
}

const METRICS = [
  { label: "Time spent searching", before: 90, after: 18, beforeLabel: "9.0 h/wk", afterLabel: "1.8 h/wk" },
  { label: "Decisions traceable", before: 12, after: 95, beforeLabel: "12%", afterLabel: "95%" },
  { label: "PRs shipped / dev / week", before: 35, after: 72, beforeLabel: "1.4", afterLabel: "2.9" },
  { label: "Cycle time (lead → done)", before: 80, after: 28, beforeLabel: "11d", afterLabel: "3.8d" },
  { label: "On-call false alerts", before: 65, after: 12, beforeLabel: "high", afterLabel: "rare" },
];
