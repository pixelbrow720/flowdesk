"use client";

import { motion } from "motion/react";

export function Pricing() {
  return (
    <section id="pricing" className="relative border-t border-[color:var(--hairline)] py-32 md:py-44">
      <div className="container-grid">
        <div className="mb-16 grid grid-cols-12 gap-6 md:mb-24">
          <div className="col-span-12 md:col-span-6">
            <span className="eyebrow">[06] Pricing</span>
            <h2 className="mt-6 text-balance text-4xl font-medium leading-[1.05] md:text-6xl">
              Two tiers. <span className="text-crimson">No seat tax.</span>
            </h2>
          </div>
          <p className="col-span-12 max-w-[42ch] text-bone-2 md:col-span-5 md:col-start-8 md:text-lg">
            We don't tax users — we charge for capacity. Your team grows; your bill behaves.
          </p>
        </div>

        <div className="grid grid-cols-12 gap-6">
          {TIERS.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "0px 0px -10% 0px" }}
              transition={{ duration: 0.9, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className={
                "relative col-span-12 flex flex-col rounded-lg border bg-ink-1 p-8 md:col-span-6 md:p-10 " +
                (t.featured
                  ? "border-crimson"
                  : "border-[color:var(--hairline-strong)]")
              }
            >
              {t.featured && (
                <span className="absolute -top-3 left-8 rounded-full bg-crimson px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-bone-0">
                  Operator
                </span>
              )}
              <div className="flex items-baseline justify-between">
                <h3 className="text-3xl font-medium md:text-4xl">{t.name}</h3>
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
                  {t.kind}
                </span>
              </div>
              <p className="mt-3 max-w-[40ch] text-bone-2">{t.copy}</p>

              <div className="mt-8 flex items-baseline gap-2">
                <span className="text-5xl font-medium md:text-6xl">{t.price}</span>
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3">
                  / {t.unit}
                </span>
              </div>

              <ul className="mt-8 space-y-3 border-t border-[color:var(--hairline)] pt-6">
                {t.features.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm text-bone-1">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-crimson" />
                    {f}
                  </li>
                ))}
              </ul>

              <a
                href="#cta"
                data-cursor="grow"
                className={
                  "mt-10 inline-flex h-12 items-center justify-center gap-3 rounded-full font-mono text-[11px] uppercase tracking-[0.18em] transition-transform hover:scale-[1.01] " +
                  (t.featured
                    ? "bg-crimson text-bone-0 hover:bg-crimson-deep"
                    : "border border-[color:var(--hairline-strong)] text-bone-0 hover:border-bone-2")
                }
              >
                {t.cta} <span>→</span>
              </a>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

const TIERS = [
  {
    name: "Studio",
    kind: "Up to 12 operators",
    copy: "For small operator teams. All four layers, capped capacity, BYOK.",
    price: "$1.2k",
    unit: "month",
    cta: "Start trial",
    featured: false,
    features: [
      "FOG · 50GB indexed corpus",
      "FLUX · 5k runs / month",
      "ARC · 4 concurrent agents",
      "Single-tenant",
      "BYOK encryption",
      "Email support",
    ],
  },
  {
    name: "Operator",
    kind: "Unlimited operators · capacity-priced",
    copy: "For real org-scale teams. Quota you set, support you talk to.",
    price: "$4.8k",
    unit: "month base",
    cta: "Request access",
    featured: true,
    features: [
      "FOG · unlimited corpus, BYOK",
      "FLUX · capacity-priced",
      "ARC · 16+ concurrent agents",
      "Single-tenant · dedicated VPC",
      "SOC2-grade controls",
      "Slack-shared engineer",
      "99.9% SLA · custom retention",
    ],
  },
];
