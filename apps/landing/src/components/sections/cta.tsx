"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { SplitText } from "@/components/atoms/split-text";

export function CTA() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const glowScale = useTransform(scrollYProgress, [0, 0.5, 1], [0.6, 1.2, 0.6]);

  return (
    <section id="cta" ref={ref} className="relative isolate overflow-hidden border-t border-[color:var(--hairline)] py-40 md:py-56">
      {/* big crimson radial */}
      <motion.div
        style={{ scale: glowScale }}
        className="pointer-events-none absolute left-1/2 top-1/2 -z-10 h-[80vmin] w-[80vmin] -translate-x-1/2 -translate-y-1/2 rounded-full"
        aria-hidden
      >
        <div
          className="h-full w-full rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(230,57,70,0.45) 0%, rgba(230,57,70,0.1) 35%, transparent 65%)",
          }}
        />
      </motion.div>

      <div className="container-grid">
        <div className="mb-12 flex items-baseline justify-between">
          <span className="eyebrow">[07] End</span>
          <span className="eyebrow text-bone-3">Or beginning</span>
        </div>

        <h2 className="text-display-1 text-balance">
          <SplitText text="Stop searching." by="word" />
          <br />
          <span className="text-crimson">
            <SplitText text="Start shipping." by="word" delay={0.2} />
          </span>
        </h2>

        <p className="mt-10 max-w-[52ch] text-lg text-bone-2 md:text-2xl">
          Paid beta is live. Single-tenant from day one. We onboard 4 teams a month, by hand.
        </p>

        <div className="mt-12 flex flex-wrap items-center gap-4">
          <a
            href="mailto:operators@flowdesk.app"
            data-cursor="grow"
            className="group relative inline-flex h-14 items-center gap-3 overflow-hidden rounded-full bg-crimson px-8 font-mono text-[11px] uppercase tracking-[0.18em] text-bone-0 transition-transform hover:scale-[1.02]"
          >
            <span className="relative z-10">operators@flowdesk.app</span>
            <span className="relative z-10">→</span>
          </a>
          <a
            href="#system"
            data-cursor="grow"
            className="inline-flex h-14 items-center gap-3 rounded-full border border-[color:var(--hairline-strong)] px-8 font-mono text-[11px] uppercase tracking-[0.18em] text-bone-1 transition-colors hover:border-bone-2"
          >
            Re-read the system <span className="text-crimson">↑</span>
          </a>
        </div>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-[color:var(--hairline)] py-12">
      <div className="container-grid">
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 md:col-span-4">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-bone-2">
                FlowDesk
              </span>
              <span className="font-mono text-[11px] text-bone-3">v0.4</span>
            </div>
            <p className="mt-3 max-w-xs text-sm text-bone-3">
              Operator-grade workspace. Built for teams that ship.
            </p>
          </div>
          <div className="col-span-6 md:col-span-2">
            <FooterCol title="Product" items={["System", "Lenses", "Workflows", "Pricing"]} />
          </div>
          <div className="col-span-6 md:col-span-2">
            <FooterCol title="Trust" items={["SOC2", "BYOK", "Status", "Security"]} />
          </div>
          <div className="col-span-6 md:col-span-2">
            <FooterCol title="Company" items={["About", "Operators", "Careers", "Contact"]} />
          </div>
          <div className="col-span-6 md:col-span-2">
            <FooterCol title="Legal" items={["Terms", "Privacy", "DPA", "Imprint"]} />
          </div>
        </div>
        <div className="mt-16 flex items-baseline justify-between border-t border-[color:var(--hairline)] pt-6 font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
          <span>© FlowDesk · {new Date().getFullYear()}</span>
          <span>Made for operators</span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, items }: { title: string; items: string[] }) {
  return (
    <>
      <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">{title}</div>
      <ul className="mt-3 space-y-2">
        {items.map((i) => (
          <li key={i}>
            <a
              href="#"
              data-cursor="grow"
              className="text-sm text-bone-2 transition-colors hover:text-bone-0"
            >
              {i}
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}
