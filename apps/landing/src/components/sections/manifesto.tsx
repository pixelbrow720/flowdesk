"use client";

import { motion } from "motion/react";
import { SplitText } from "@/components/atoms/split-text";

export function Manifesto() {
  return (
    <section className="relative border-t border-[color:var(--hairline)] py-32 md:py-44">
      <div className="container-grid">
        <div className="mb-16 flex items-baseline justify-between md:mb-24">
          <span className="eyebrow">[01] Position</span>
          <span className="eyebrow text-bone-3">Manifesto</span>
        </div>

        <h2 className="text-display-2 text-balance">
          <SplitText text="Most workspaces optimize" by="word" />
          <br />
          <span className="text-bone-3">
            <SplitText text="for participation." by="word" delay={0.1} />
          </span>
          <br />
          <SplitText text="We optimize for" by="word" delay={0.2} />{" "}
          <span className="text-crimson">
            <SplitText text="output." by="word" delay={0.3} />
          </span>
        </h2>

        <div className="mt-20 grid grid-cols-12 gap-6 md:mt-32">
          {pillars.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "0px 0px -10% 0px" }}
              transition={{ duration: 0.9, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="col-span-12 border-t border-[color:var(--hairline-strong)] pt-6 md:col-span-4"
            >
              <div className="mb-6 flex items-center gap-3">
                <span className="font-mono text-[11px] text-crimson">{p.id}</span>
                <span className="eyebrow">{p.kicker}</span>
              </div>
              <h3 className="mb-3 text-2xl font-medium text-bone-0 md:text-3xl">{p.title}</h3>
              <p className="text-base leading-relaxed text-bone-2">{p.copy}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

const pillars = [
  {
    id: "01",
    kicker: "Decision",
    title: "Context, not chat.",
    copy: "FOG indexes every artifact, message, and decision. Every prompt arrives loaded. No more 'where was that link.'",
  },
  {
    id: "02",
    kicker: "Execution",
    title: "Determinism over magic.",
    copy: "FLUX runs typed workflows you can read, version, and replay. Side-effects logged. No agent hallucinations in prod.",
  },
  {
    id: "03",
    kicker: "Signal",
    title: "Operator dashboards.",
    copy: "Velocity, blockers, throughput — surfaced. The view your CTO actually opens at 8am, not the kanban graveyard.",
  },
];
