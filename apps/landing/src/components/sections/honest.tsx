"use client";

/**
 * HONEST — receipts table. Trust builder.
 *
 * Per-row SWEEP aura: brick gradient travels left→right then fades through —
 * "smoke passing", not a persistent fill (a fill would dominate a thin row).
 * Headlines white. Static aura removed (cursor trigger replaces ambient).
 */

import { motion } from "framer-motion";
import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";
import { HoverAura } from "@/components/atoms/hover-aura";

export function Honest() {
  const lang = useLang();
  return (
    <section id="honest" className="relative bg-ink-0 py-28 md:py-40">
      <div className="container-grid">
        <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
          <span>{t(lang, copy.honest.eyebrow)}</span>
          <span className="hidden md:inline">{t(lang, copy.honest.eyebrowRight)}</span>
        </div>
        <motion.h2
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 font-display text-display-2 leading-[0.96] tracking-[-0.02em] text-bone-0"
        >
          <span className="block">{t(lang, copy.honest.headline1)}</span>
          <span className="block">{t(lang, copy.honest.headline2)}</span>
        </motion.h2>
        <p className="mt-8 max-w-2xl text-[17px] leading-relaxed text-bone-2">
          {t(lang, copy.honest.lede)}
        </p>

        {/* Table */}
        <div className="mt-16 overflow-hidden rounded-sm border border-[color:var(--hairline-strong)] bg-ink-0">
          <dl className="divide-y divide-[color:var(--hairline)]">
            {copy.honest.rows.map((row, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-5%" }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: i * 0.03 }}
                className="group relative isolate grid grid-cols-1 gap-2 overflow-hidden px-6 py-5 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] md:gap-8 md:px-8"
              >
                <HoverAura variant="sweep" />
                <dt className="font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3 transition-colors group-hover:text-bone-0">
                  {t(lang, row.k)}
                </dt>
                <dd className="font-mono text-[13px] text-bone-1">{row.v}</dd>
              </motion.div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
