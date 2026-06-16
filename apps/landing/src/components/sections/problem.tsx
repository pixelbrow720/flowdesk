"use client";

/**
 * PROBLEM — the marketing wedge. Agitates before we sell.
 * Headlines both white. Cursor smoke + per-card HoverAura(stay) provide brick.
 */

import { motion } from "framer-motion";
import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";
export function Problem() {
  const lang = useLang();
  return (
    <section id="problem" className="relative bg-ink-0 py-28 md:py-40">
      <div className="container-grid">
        {/* Eyebrow row */}
        <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
          <span>{t(lang, copy.problem.eyebrow)}</span>
          <span className="hidden md:inline">{t(lang, copy.problem.eyebrowRight)}</span>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <motion.h2
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-15%" }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-display-2 leading-[0.96] tracking-[-0.02em] text-bone-0"
          >
            <span className="block">{t(lang, copy.problem.headline1)}</span>
            <span className="block text-brick">{t(lang, copy.problem.headline2)}</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-15%" }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
            className="self-end pb-3 text-[17px] leading-relaxed text-bone-2"
          >
            {t(lang, copy.problem.lede)}
          </motion.p>
        </div>

        {/* Three bullets — HoverAura stay */}
        <div className="mt-20 grid grid-cols-1 gap-px bg-[color:var(--hairline)] md:grid-cols-3">
          {copy.problem.bullets.map((b, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-15%" }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: i * 0.08 }}
              className="group relative isolate overflow-hidden bg-ink-0 p-8 md:p-10 aura-stay"
            >
              <span className="pointer-events-none absolute left-0 top-0 h-full w-[2px] origin-top scale-y-0 bg-brick transition-transform duration-500 group-hover:scale-y-100" />
              <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
                0{i + 1}
              </div>
              <h3 className="mt-6 font-display text-2xl leading-[1.08] text-bone-0 md:text-3xl">
                {t(lang, b.h)}
              </h3>
              <p className="mt-4 text-[15px] leading-relaxed text-bone-2">{t(lang, b.b)}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
