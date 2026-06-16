"use client";

/**
 * FLOW — pipeline stages. Headlines white, HoverAura per node, no static aura.
 */

import { motion } from "framer-motion";
import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";
export function Flow() {
  const lang = useLang();
  return (
    <section id="flow" className="relative bg-ink-0 py-28 md:py-40">
      <div className="container-grid">
        <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
          {t(lang, copy.flow.eyebrow)}
        </div>
        <motion.h2
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 font-display text-display-2 leading-[0.96] tracking-[-0.02em] text-bone-0"
        >
          <span className="block">{t(lang, copy.flow.headline1)}</span>
          <span className="block">{t(lang, copy.flow.headline2)}</span>
        </motion.h2>
        <p className="mt-8 max-w-2xl text-[17px] leading-relaxed text-bone-2">
          {t(lang, copy.flow.lede)}
        </p>

        <ol className="mt-20 grid grid-cols-1 gap-px bg-[color:var(--hairline)] md:grid-cols-2 lg:grid-cols-4">
          {copy.flow.nodes.map((n, i) => (
            <motion.li
              key={n.id}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: (i % 4) * 0.05 }}
              className="group relative isolate overflow-hidden bg-ink-0 p-7 md:p-8 aura-stay"
            >
              <span className="pointer-events-none absolute left-0 top-0 h-full w-[2px] origin-top scale-y-0 bg-brick transition-transform duration-500 group-hover:scale-y-100" />
              <div className="flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.22em] text-bone-3">
                <span>{String(i + 1).padStart(2, "0")}</span>
                <span>{t(lang, n.kind)}</span>
              </div>
              <div className="mt-6 font-display text-2xl leading-[1.1] text-bone-0 transition-colors group-hover:text-brick">
                {n.id}
              </div>
              <p className="mt-3 font-mono text-[11.5px] uppercase tracking-[0.18em] text-bone-2">
                {n.detail}
              </p>
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  );
}
