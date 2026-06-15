"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";

/**
 * HORIZONTAL PIN — the Circle-style move.
 *
 * Mechanic:
 * - Outer wrapper has explicit height = (panels * 100vh) + buffer.
 * - Sticky inner pins at top:0, full viewport.
 * - useScroll measures progress over the outer wrapper.
 * - We translateX the rail by -((N-1) / N * 100%) over progress 0→1.
 *
 * Result: as you scroll vertically, panels slide horizontally.
 * On mobile (< md) we collapse to vertical stack — no pin (better UX).
 */
export function Lenses() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });

  // 7 panels = move (6/7) * 100% = ~85.71% to land last panel
  const x = useTransform(scrollYProgress, [0, 1], ["0%", `-${((LENSES.length - 1) / LENSES.length) * 100}%`]);

  // header progress bar
  const progressWidth = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);

  return (
    <section id="lenses" className="relative border-t border-[color:var(--hairline)]">
      {/* Mobile fallback: vertical stack */}
      <div className="container-grid block py-24 md:hidden">
        <SectionHeader />
        <div className="mt-12 space-y-6">
          {LENSES.map((l) => (
            <LensCard key={l.id} lens={l} compact />
          ))}
        </div>
      </div>

      {/* Desktop: horizontal pin */}
      <div ref={ref} className="relative hidden md:block" style={{ height: `${LENSES.length * 100}vh` }}>
        <div className="sticky top-0 flex h-screen flex-col overflow-hidden">
          {/* sticky header */}
          <div className="container-grid flex-shrink-0 border-b border-[color:var(--hairline)] py-8">
            <div className="mb-6 flex items-baseline justify-between">
              <span className="eyebrow">[02] Lenses</span>
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
                Scroll → to navigate
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-6">
              <h2 className="text-3xl font-medium tracking-snug text-balance md:text-4xl lg:text-5xl">
                Seven lenses on the same <span className="text-crimson">graph of work.</span>
              </h2>
              {/* progress bar */}
              <div className="hidden h-px w-48 flex-shrink-0 bg-[color:var(--hairline-strong)] lg:block">
                <motion.div className="h-full bg-crimson" style={{ width: progressWidth }} />
              </div>
            </div>
          </div>

          {/* horizontal rail */}
          <div className="flex-1 overflow-hidden">
            <motion.div
              style={{ x, width: `${LENSES.length * 100}%` }}
              className="flex h-full"
            >
              {LENSES.map((l, i) => (
                <div key={l.id} style={{ width: `${100 / LENSES.length}%` }} className="h-full">
                  <LensCard lens={l} index={i} />
                </div>
              ))}
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SectionHeader() {
  return (
    <>
      <div className="mb-6 flex items-baseline justify-between">
        <span className="eyebrow">[02] Lenses</span>
        <span className="eyebrow text-bone-3">7 views</span>
      </div>
      <h2 className="text-3xl font-medium tracking-snug text-balance md:text-5xl">
        Seven lenses on the same <span className="text-crimson">graph of work.</span>
      </h2>
    </>
  );
}

function LensCard({ lens, index = 0, compact = false }: { lens: (typeof LENSES)[number]; index?: number; compact?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className={
        compact
          ? "rounded-lg border border-[color:var(--hairline)] bg-ink-1 p-6"
          : "container-grid grid h-full grid-cols-12 items-center gap-10 py-12"
      }
    >
      {/* big numeral */}
      <div className={compact ? "mb-4 flex items-baseline gap-3" : "col-span-5"}>
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[11px] text-crimson">
            0{index + 1} / 0{LENSES.length}
          </span>
          <span className="eyebrow text-bone-3">{lens.tag}</span>
        </div>
        {!compact && (
          <div className="mt-8 font-mono text-[clamp(7rem,18vw,16rem)] leading-none text-bone-3/30">
            {String(index + 1).padStart(2, "0")}
          </div>
        )}
      </div>

      {/* content */}
      <div className={compact ? "" : "col-span-7"}>
        <h3
          className={
            compact
              ? "mb-2 text-2xl font-medium text-bone-0"
              : "mb-6 text-balance text-4xl font-medium leading-[1.05] text-bone-0 lg:text-6xl"
          }
        >
          {lens.title}
        </h3>
        <p className={compact ? "text-sm text-bone-2" : "max-w-[52ch] text-lg text-bone-2 lg:text-xl"}>
          {lens.copy}
        </p>

        {/* hardware-style spec sheet */}
        <div className={compact ? "mt-4 grid grid-cols-2 gap-3" : "mt-10 grid grid-cols-2 gap-px overflow-hidden rounded border border-[color:var(--hairline)] bg-[color:var(--hairline)] md:max-w-md"}>
          {lens.specs.map(([k, v]) => (
            <div key={k} className={compact ? "" : "bg-ink-0 p-4"}>
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-bone-3">
                {k}
              </div>
              <div className="mt-1 font-mono text-sm text-bone-0">{v}</div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

const LENSES = [
  {
    id: "decisions",
    tag: "Decisions",
    title: "Every call, traceable.",
    copy: "Decisions become first-class objects — not buried in DMs. Linked to the artifacts, the people, the why.",
    specs: [
      ["Object", "Decision"],
      ["Linked", "Artifacts · People"],
      ["Lens", "Decision Log"],
      ["Audit", "Replayable"],
    ] as [string, string][],
  },
  {
    id: "execution",
    tag: "Execution",
    title: "Workflows that ship.",
    copy: "FLUX runs typed graphs. Versioned. Side-effects logged. No agent hallucinations in production.",
    specs: [
      ["Object", "Workflow"],
      ["Type", "DAG · Typed"],
      ["Lens", "Execution"],
      ["Replay", "Yes"],
    ] as [string, string][],
  },
  {
    id: "signal",
    tag: "Signal",
    title: "Operator dashboards.",
    copy: "Velocity, blockers, throughput — surfaced. The view your CTO opens at 8am, not the kanban graveyard.",
    specs: [
      ["Object", "Metric"],
      ["Cadence", "Real-time"],
      ["Lens", "Signal"],
      ["Alerts", "Smart"],
    ] as [string, string][],
  },
  {
    id: "context",
    tag: "Context",
    title: "FOG — the engine.",
    copy: "Every artifact indexed, every prompt arrives loaded. Search becomes recall, recall becomes leverage.",
    specs: [
      ["Engine", "FOG"],
      ["Index", "Vector + Graph"],
      ["Lens", "Context"],
      ["Latency", "<200ms"],
    ] as [string, string][],
  },
  {
    id: "agents",
    tag: "Agents",
    title: "ARC orchestration.",
    copy: "Multi-agent, scoped, deterministic. Each agent inherits FOG context, runs FLUX workflows, reports to OUTPUT.",
    specs: [
      ["Engine", "ARC"],
      ["Concurrency", "Bounded"],
      ["Lens", "Agents"],
      ["Sandbox", "Per-task"],
    ] as [string, string][],
  },
  {
    id: "trust",
    tag: "Trust",
    title: "Single-tenant by default.",
    copy: "Your data stays on your boundary. SOC2-grade controls, BYOK, audit trails that satisfy enterprise.",
    specs: [
      ["Tenancy", "Single"],
      ["Encryption", "BYOK"],
      ["Lens", "Audit"],
      ["Compliance", "SOC2"],
    ] as [string, string][],
  },
  {
    id: "speed",
    tag: "Speed",
    title: "Operator pace.",
    copy: "Keyboard-first. Sub-100ms interactions. Built for people who treat their tools like instruments.",
    specs: [
      ["Input", "⌘K · Vim"],
      ["P95", "<80ms"],
      ["Lens", "Speed"],
      ["Offline", "First-class"],
    ] as [string, string][],
  },
];
