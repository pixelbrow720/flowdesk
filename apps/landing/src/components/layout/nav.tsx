"use client";

/**
 * Nav — minimal. NO Discord login button (single CTA lives at bottom Access).
 * Just wordmark + section anchors + EN/ID toggle + ghost "Get access" that
 * scroll-jumps to #access (so visitors funnel through the story first).
 */

import { useLang, useSetLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";

export function Nav() {
  const lang = useLang();
  const setLang = useSetLang();

  return (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-[color:var(--hairline)] bg-ink-0/70 backdrop-blur-md">
      <div className="container-grid flex h-14 items-center justify-between">
        {/* Wordmark */}
        <a href="#top" className="flex items-center gap-2.5 font-mono text-[12px] uppercase tracking-[0.22em]">
          <span className="grid h-3 w-3 place-items-center">
            <span className="h-2 w-2 bg-brick" />
          </span>
          <span className="text-bone-0">FlowDesk</span>
        </a>

        {/* Section anchors — desktop */}
        <nav className="hidden items-center gap-7 font-mono text-[11px] uppercase tracking-[0.22em] text-bone-2 md:flex">
          <a href="#system" className="transition-colors hover:text-bone-0">{t(lang, copy.nav.system)}</a>
          <a href="#lenses" className="transition-colors hover:text-bone-0">{t(lang, copy.nav.lenses)}</a>
          <a href="#flow" className="transition-colors hover:text-bone-0">{t(lang, copy.nav.flow)}</a>
          <a href="#access" className="transition-colors hover:text-bone-0">{t(lang, copy.nav.access)}</a>
        </nav>

        {/* Right cluster — locale toggle + ghost access link (scroll-jump only) */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-0 rounded-full border border-[color:var(--hairline)] p-0.5 font-mono text-[10px] uppercase tracking-[0.2em]">
            <button
              type="button"
              onClick={() => setLang("en")}
              aria-pressed={lang === "en"}
              className={`px-2.5 py-1 rounded-full transition-colors ${lang === "en" ? "bg-bone-0 text-ink-0" : "text-bone-2 hover:text-bone-0"}`}
            >EN</button>
            <button
              type="button"
              onClick={() => setLang("id")}
              aria-pressed={lang === "id"}
              className={`px-2.5 py-1 rounded-full transition-colors ${lang === "id" ? "bg-bone-0 text-ink-0" : "text-bone-2 hover:text-bone-0"}`}
            >ID</button>
          </div>
          <a
            href="#access"
            className="hidden font-mono text-[11px] uppercase tracking-[0.22em] text-bone-2 transition-colors hover:text-bone-0 sm:inline-block"
          >
            {t(lang, copy.nav.cta)} ↓
          </a>
        </div>
      </div>
    </header>
  );
}
