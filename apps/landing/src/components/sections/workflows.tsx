"use client";

import { motion } from "motion/react";
import { useState } from "react";
import clsx from "clsx";

/**
 * WORKFLOWS — interactive node graph illustration.
 * Hover/tap a workflow on the left → diagram on the right re-orders.
 */
export function Workflows() {
  const [active, setActive] = useState(0);
  const w = WORKFLOWS[active];

  return (
    <section id="workflows" className="relative border-t border-[color:var(--hairline)] py-32 md:py-44">
      <div className="container-grid">
        <div className="mb-16 grid grid-cols-12 gap-6 md:mb-24">
          <div className="col-span-12 md:col-span-6">
            <span className="eyebrow">[04] FLUX</span>
            <h2 className="mt-6 text-balance text-4xl font-medium leading-[1.05] md:text-6xl">
              Workflows you can <span className="text-brick">read.</span>
            </h2>
          </div>
          <p className="col-span-12 max-w-[44ch] text-bone-2 md:col-span-5 md:col-start-8 md:text-lg">
            Typed graph. Versioned in git. Replayable. Side-effects logged. The opposite of a
            no-code black box.
          </p>
        </div>

        <div className="grid grid-cols-12 gap-10">
          {/* selector list */}
          <div className="col-span-12 lg:col-span-5">
            <ul className="space-y-2">
              {WORKFLOWS.map((wf, i) => (
                <li key={wf.id}>
                  <button
                    onClick={() => setActive(i)}
                    onMouseEnter={() => setActive(i)}
                    data-cursor="grow"
                    className={clsx(
                      "group flex w-full items-center justify-between gap-6 border-b border-[color:var(--hairline)] py-5 text-left transition-colors",
                      active === i ? "text-bone-0" : "text-bone-3 hover:text-bone-1"
                    )}
                  >
                    <span className="flex items-baseline gap-4">
                      <span className="font-mono text-[11px] text-brick">
                        0{i + 1}
                      </span>
                      <span className="text-2xl font-medium md:text-3xl">{wf.name}</span>
                    </span>
                    <motion.span
                      animate={{ x: active === i ? 0 : -8, opacity: active === i ? 1 : 0 }}
                      className="text-teal-glow"
                    >
                      →
                    </motion.span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* diagram */}
          <div className="col-span-12 lg:col-span-7">
            <div className="rounded-lg border border-[color:var(--hairline-strong)] bg-ink-1 p-8">
              <div className="mb-6 flex items-baseline justify-between">
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
                  flux/workflows/{w.id}.flux.ts
                </span>
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-teal-glow">
                  ● typed
                </span>
              </div>

              {/* nodes */}
              <div className="space-y-3">
                {w.nodes.map((n, i) => (
                  <motion.div
                    key={`${w.id}-${n.label}`}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
                    className="flex items-center gap-4"
                  >
                    <span className="font-mono text-[11px] text-bone-3 w-6">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div className="flex-1 rounded border border-[color:var(--hairline)] bg-ink-2 px-4 py-3">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm text-bone-0">{n.label}</span>
                        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-teal-glow">
                          {n.kind}
                        </span>
                      </div>
                      {n.note && (
                        <div className="mt-1 font-mono text-[11px] text-bone-3">{n.note}</div>
                      )}
                    </div>
                    {i < w.nodes.length - 1 && (
                      <span className="hidden font-mono text-bone-3 md:block">↓</span>
                    )}
                  </motion.div>
                ))}
              </div>

              <div className="mt-6 grid grid-cols-3 gap-px overflow-hidden rounded border border-[color:var(--hairline)] bg-[color:var(--hairline)]">
                {w.specs.map(([k, v]) => (
                  <div key={k} className="bg-ink-1 p-3">
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-bone-3">
                      {k}
                    </div>
                    <div className="mt-1 font-mono text-sm text-bone-0">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

const WORKFLOWS = [
  {
    id: "incident-triage",
    name: "Incident triage",
    nodes: [
      { label: "alert.received", kind: "trigger", note: "PagerDuty webhook" },
      { label: "fog.recall(playbook)", kind: "context", note: "<200ms" },
      { label: "arc.dispatch(triage_agent)", kind: "agent", note: "bounded · 1" },
      { label: "decision.log", kind: "side-effect", note: "audit trail" },
      { label: "output.dashboard.update", kind: "surface" },
    ],
    specs: [
      ["Runtime", "FLUX"],
      ["P95", "1.2s"],
      ["Replay", "Yes"],
    ] as [string, string][],
  },
  {
    id: "release-cut",
    name: "Release cut",
    nodes: [
      { label: "schedule.tuesday_10am", kind: "trigger" },
      { label: "fog.diff(last_release..HEAD)", kind: "context" },
      { label: "arc.dispatch(release_notes_agent)", kind: "agent" },
      { label: "approval.request(eng_lead)", kind: "human" },
      { label: "github.create_release", kind: "side-effect" },
    ],
    specs: [
      ["Runtime", "FLUX"],
      ["P95", "8s"],
      ["Replay", "Yes"],
    ] as [string, string][],
  },
  {
    id: "weekly-signal",
    name: "Weekly signal",
    nodes: [
      { label: "cron.monday_8am", kind: "trigger" },
      { label: "output.collect_metrics", kind: "context" },
      { label: "arc.dispatch(synth_agent)", kind: "agent" },
      { label: "decision.log(blockers)", kind: "side-effect" },
      { label: "slack.post(#operators)", kind: "surface" },
    ],
    specs: [
      ["Runtime", "FLUX"],
      ["P95", "3.4s"],
      ["Replay", "Yes"],
    ] as [string, string][],
  },
  {
    id: "decision-capture",
    name: "Decision capture",
    nodes: [
      { label: "thread.flagged(decision)", kind: "trigger" },
      { label: "fog.gather(thread, links)", kind: "context" },
      { label: "arc.dispatch(synth_agent)", kind: "agent" },
      { label: "decision.create", kind: "side-effect" },
      { label: "output.decision_log", kind: "surface" },
    ],
    specs: [
      ["Runtime", "FLUX"],
      ["P95", "2.1s"],
      ["Replay", "Yes"],
    ] as [string, string][],
  },
];
