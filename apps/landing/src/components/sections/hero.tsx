"use client";

/**
 * HERO — solid black BG. Headline1 white, headline2 brick.
 * Headline leading 0.92 for descender clearance (p, g, y, q).
 */

import { motion } from "framer-motion";
import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";

export function Hero() {
  const lang = useLang();

  return (
    <section id="top" className="relative isolate overflow-hidden bg-ink-0">
      <div className="container-grid relative pt-32 pb-12 md:pt-40 md:pb-16">
        {/* Eyebrow status line — terminal-ish */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[10.5px] uppercase tracking-[0.22em] text-bone-3">
          <span className="flex items-center gap-2">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-brick shadow-[0_0_10px_rgba(184,51,62,0.7)]" />
            {t(lang, copy.hero.eyebrowBeta)}
          </span>
          <span className="hidden h-px w-8 bg-[color:var(--hairline)] sm:inline-block" />
          <span>{t(lang, copy.hero.eyebrowScope)}</span>
        </div>

        {/* Main composition */}
        <div className="mt-16 grid grid-cols-1 items-end gap-x-10 gap-y-10 md:mt-24 md:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          {/* Headline — line 1 white, line 2 brick. */}
          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-display-1 leading-[0.92] tracking-[-0.04em] text-bone-0"
          >
            <span className="block">{t(lang, copy.hero.headline1)}</span>
            <span className="block text-brick">{t(lang, copy.hero.headline2)}</span>
          </motion.h1>

          {/* Right column: subhead + scroll hint. */}
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
            className="max-w-md pb-2 md:pb-4"
          >
            <p className="text-base leading-relaxed text-bone-2 md:text-[17px]">
              {t(lang, copy.hero.sub)}
            </p>
            <a
              href="#problem"
              className="mt-7 inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.22em] text-bone-1 underline decoration-bone-3 decoration-2 underline-offset-[6px] transition-colors hover:text-bone-0 hover:decoration-brick"
            >
              {t(lang, copy.hero.scrollHint)} <span aria-hidden>↓</span>
            </a>
          </motion.div>
        </div>

        {/* Bottom services ticker */}
        <div className="mt-20 border-t border-[color:var(--hairline)] pt-5 md:mt-28">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-2 font-mono text-[10.5px] uppercase tracking-[0.22em] text-bone-3">
            {copy.hero.ticker.map((item, i) => (
              <span key={item} className="flex items-center gap-2">
                <span>{item}</span>
                {i < copy.hero.ticker.length - 1 ? <span className="text-bone-3/50">·</span> : null}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
