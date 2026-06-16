"use client";

/**
 * SYSTEM — three engines, one Snapshot. The technical reveal.
 * Headlines white. Engine IDs (FOG/FLUX/ARC) white. Cursor smoke + HoverAura(stay).
 */

import { motion } from "framer-motion";
import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";
export function System() {
  const lang = useLang();
  return (
    <section id="system" className="relative bg-ink-0 py-28 md:py-40">
      <div className="container-grid">
        <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
          {t(lang, copy.system.eyebrow)}
        </div>

        <motion.h2
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 font-display text-display-2 leading-[0.96] tracking-[-0.02em] text-bone-0"
        >
          <span className="block">{t(lang, copy.system.headline1)}</span>
          <span className="block text-brick">{t(lang, copy.system.headline2)}</span>
        </motion.h2>
        <p className="mt-8 max-w-2xl text-[17px] leading-relaxed text-bone-2">
          {t(lang, copy.system.lede)}
        </p>

        {/* Three layer cards */}
        <div className="mt-20 grid grid-cols-1 gap-px bg-[color:var(--hairline)] md:grid-cols-3">
          {copy.system.layers.map((layer, i) => (
            <motion.article
              key={layer.id}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-15%" }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: i * 0.1 }}
              className="group relative isolate overflow-hidden bg-ink-0 p-8 md:p-10 aura-stay"
            >
              <span className="pointer-events-none absolute left-0 top-0 h-full w-[2px] origin-top scale-y-0 bg-brick transition-transform duration-500 group-hover:scale-y-100" />
              <div className="flex items-baseline justify-between font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
                <span>0{i + 1}</span>
                <span className="text-bone-2">{t(lang, layer.kind)}</span>
              </div>
              <div className="mt-6 font-mono text-2xl tracking-[0.04em] text-bone-0 transition-colors group-hover:text-brick">
                {layer.id}
              </div>
              <p className="mt-3 font-display text-xl leading-[1.15] text-bone-0">
                {t(lang, layer.tagline)}
              </p>
              <p className="mt-5 text-[14.5px] leading-relaxed text-bone-2">
                {t(lang, layer.copy)}
              </p>
              <div className="mt-7 flex flex-wrap gap-1.5">
                {layer.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-[color:var(--hairline-strong)] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-bone-2"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </motion.article>
          ))}
        </div>

        {/* Snapshot note */}
        <p className="mt-12 max-w-3xl border-l-2 border-bone-3 pl-5 text-[15px] leading-relaxed text-bone-2 transition-colors hover:border-brick">
          {t(lang, copy.system.snapshotNote)}
        </p>
      </div>
    </section>
  );
}
