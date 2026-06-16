"use client";

/**
 * LENSES — HORIZONTAL PINNED SCROLL.
 *
 * Mechanics:
 *   - Outer wrapper: tall (N * 100vh) so vertical scroll pans horizontally.
 *   - Inner sticky: 100vh, holds a horizontal track translated by scroll progress.
 *   - Each card: tight width (min(720px, 78vw)) + small gap → cards feel adjacent,
 *     not isolated. Earlier 100vw per card created excessive negative space.
 *   - Progress bar at bottom (01..0N + brick fill).
 *   - HoverAura(stay) per card. Cursor-trigger smoke handles ambient brick.
 *   - Static brick aura behind headline: REMOVED (cursor trigger replaces it).
 *
 * Mobile (<md): vertical stack fallback (touch-fragile pinning).
 */

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";
// Card geometry (desktop). Keep cards close: ~520px wide on big screens with a
// thin gap between them. Track width = N * (cardW + gap).
const CARD_W = "min(560px, 72vw)";
const GAP = "1.5vw";

export function Lenses() {
  const lang = useLang();
  const items = copy.lenses.items;
  const N = items.length;

  const wrapperRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: wrapperRef,
    offset: ["start start", "end end"],
  });

  // Translate the track from 0 to -(N-1)/N * 100% so the last card lands flush.
  const translateX = useTransform(
    scrollYProgress,
    [0, 1],
    ["0%", `-${((N - 1) / N) * 100}%`],
  );

  const activeIndex = useTransform(scrollYProgress, (p) =>
    Math.min(N - 1, Math.max(0, Math.floor(p * N))),
  );

  return (
    <section id="lenses" className="relative bg-ink-0">
      {/* Intro block — vertical, before pinned scroll begins. */}
      <div className="container-grid pt-28 md:pt-40">
        <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3">
          <span>{t(lang, copy.lenses.eyebrow)}</span>
          <span className="hidden md:inline">{t(lang, copy.lenses.eyebrowRight)}</span>
        </div>

        <motion.h2
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15%" }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 font-display text-display-2 leading-[0.96] tracking-[-0.02em] text-bone-0"
        >
          <span className="block">{t(lang, copy.lenses.headline1)}</span>
          <span className="block">{t(lang, copy.lenses.headline2)}</span>
        </motion.h2>

        <div className="mt-10 flex items-center gap-3 font-mono text-[10.5px] uppercase tracking-[0.22em] text-bone-3 md:hidden">
          <span>↓ scroll — cards stack</span>
        </div>
        <div className="mt-10 hidden items-center gap-3 font-mono text-[10.5px] uppercase tracking-[0.22em] text-bone-3 md:flex">
          <span>↓ scroll vertically</span>
          <span className="h-px w-10 bg-[color:var(--hairline)]" />
          <span>cards pan right →</span>
        </div>
      </div>

      {/* MOBILE fallback */}
      <div className="container-grid mt-12 grid grid-cols-1 gap-px bg-[color:var(--hairline)] md:hidden">
        {items.map((item, i) => (
          <LensCard key={item.no} item={item} index={i} lang={lang} active />
        ))}
      </div>

      {/* DESKTOP horizontal pinned scroll. */}
      <div
        ref={wrapperRef}
        className="relative mt-16 hidden md:block"
        style={{ height: `${N * 100}vh` }}
      >
        <div className="sticky top-0 flex h-screen items-center overflow-hidden">
          <motion.div
            style={{ x: translateX, gap: GAP }}
            className="flex h-[78%] items-stretch pl-[6vw] will-change-transform"
          >
            {items.map((item, i) => (
              <div
                key={item.no}
                className="h-full shrink-0"
                style={{ width: CARD_W }}
              >
                <LensCard item={item} index={i} lang={lang} active />
              </div>
            ))}
          </motion.div>

          {/* Progress bar */}
          <div className="pointer-events-none absolute bottom-10 left-0 right-0 px-[6vw]">
            <div className="flex items-center gap-4 font-mono text-[10.5px] uppercase tracking-[0.22em] text-bone-3">
              <motion.span className="tabular-nums text-bone-0">
                <ActiveCounter index={activeIndex} total={N} />
              </motion.span>
              <div className="relative h-px flex-1 bg-[color:var(--hairline)]">
                <motion.div
                  style={{ scaleX: scrollYProgress }}
                  className="absolute inset-0 origin-left bg-brick"
                />
              </div>
              <span className="tabular-nums">{String(N).padStart(2, "0")}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- */

function ActiveCounter({
  index,
  total,
}: {
  index: ReturnType<typeof useTransform<number, number>>;
  total: number;
}) {
  const text = useTransform(index, (i) =>
    String(Math.min(total, Math.max(1, Math.floor(i) + 1))).padStart(2, "0"),
  );
  return <motion.span>{text}</motion.span>;
}

function LensCard({
  item,
  index: _index,
  lang,
  active,
}: {
  item: (typeof copy.lenses.items)[number];
  index: number;
  lang: ReturnType<typeof useLang>;
  active: boolean;
}) {
  const isExp = item.status === "EXPERIMENTAL";
  return (
    <article className="group relative isolate flex h-full w-full flex-col justify-between overflow-hidden border border-[color:var(--hairline)] bg-ink-0 p-8 md:p-10 aura-stay">
      <span
        className={`pointer-events-none absolute left-0 top-0 h-full w-[2px] origin-top bg-brick transition-transform duration-500 ${
          active ? "scale-y-100" : "scale-y-0"
        }`}
      />

      <div>
        <div
          className="font-display text-[110px] leading-none tracking-tight text-bone-2/20 md:text-[160px]"
          aria-hidden
        >
          {item.no}
        </div>

        <div className="mt-6 flex items-center gap-2">
          <span className="inline-block rounded-full border border-bone-3 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-bone-0 transition-colors group-hover:border-brick group-hover:text-brick">
            {t(lang, item.tag)}
          </span>
          {isExp ? (
            <span className="inline-block rounded-full border border-bone-3/60 px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.22em] text-bone-2">
              Experimental
            </span>
          ) : null}
        </div>

        <h3 className="mt-6 max-w-xl font-display text-[28px] leading-[1.1] text-bone-0 md:text-[32px]">
          {t(lang, item.title)}
        </h3>

        <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-bone-2 md:text-[16px]">
          {t(lang, item.copy)}
        </p>
      </div>

      <div className="mt-10 flex max-w-xl items-center justify-between border-t border-[color:var(--hairline)] pt-5 font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3">
        <span>{item.status}</span>
        <span aria-hidden className="text-bone-3 transition-colors group-hover:text-brick">→</span>
      </div>
    </article>
  );
}
