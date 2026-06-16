"use client";

/**
 * ACCESS — the single CTA section (terminal stop of the page).
 * Headline both white. Static aura removed. Bullets gain HoverAura(sweep).
 * Primary CTA keeps brick fill — that's an action, not a passive headline.
 */

import { motion } from "framer-motion";
import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";
export function Access() {
  const lang = useLang();
  return (
    <section id="access" className="relative bg-ink-0 py-32 md:py-44">
      <div className="container-grid">
        <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
          {t(lang, copy.access.eyebrow)}
        </div>

        <motion.h2
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 font-display text-display-1 leading-[0.96] tracking-[-0.035em] text-bone-0"
        >
          <span className="block">{t(lang, copy.access.headline1)}</span>
          <span className="block">{t(lang, copy.access.headline2)}</span>
        </motion.h2>

        <p className="mt-10 max-w-2xl text-[18px] leading-relaxed text-bone-2">
          {t(lang, copy.access.lede)}
        </p>

        {/* Bullets — sweep aura on hover */}
        <ul className="mt-12 grid grid-cols-1 gap-px bg-[color:var(--hairline)] md:grid-cols-2">
          {copy.access.bullets.map((b, i) => (
            <li
              key={i}
              className="group relative isolate flex items-center gap-4 overflow-hidden bg-ink-0 px-6 py-5 aura-sweep"
            >
              <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-bone-0 transition-colors group-hover:text-brick">
                0{i + 1}
              </span>
              <span className="font-mono text-[12.5px] uppercase tracking-[0.18em] text-bone-1">
                {t(lang, b)}
              </span>
            </li>
          ))}
        </ul>

        {/* CTAs */}
        <div className="mt-16 flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:gap-5">
          <a
            href="/api/auth/discord/login"
            className="group inline-flex items-center gap-3 rounded-sm bg-brick px-7 py-4 font-mono text-[12px] uppercase tracking-[0.22em] text-bone-0 transition-colors hover:bg-brick-glow"
          >
            <span>{t(lang, copy.access.ctaPrimary)}</span>
            <span aria-hidden className="transition-transform group-hover:translate-x-0.5">→</span>
          </a>
          <a
            href="https://flowjob.id"
            target="_blank"
            rel="noreferrer noopener"
            className="group inline-flex items-center gap-3 rounded-sm border border-[color:var(--hairline-strong)] px-7 py-4 font-mono text-[12px] uppercase tracking-[0.22em] text-bone-1 transition-colors hover:border-brick hover:text-brick"
          >
            <span>{t(lang, copy.access.ctaSecondary)}</span>
            <span aria-hidden className="transition-transform group-hover:translate-x-0.5">↗</span>
          </a>
        </div>

        <p className="mt-10 max-w-3xl font-mono text-[11px] uppercase leading-relaxed tracking-[0.18em] text-bone-3">
          {t(lang, copy.access.legal)}
        </p>
      </div>
    </section>
  );
}
