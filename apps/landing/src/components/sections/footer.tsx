"use client";

/**
 * FOOTER — minimal. No CTAs (those live exclusively in #access).
 * Just wordmark, tagline, link columns, legal line.
 */

import { useLang, t } from "@/lib/i18n";
import { copy } from "@/lib/copy";

export function Footer() {
  const lang = useLang();
  return (
    <footer className="bg-ink-0 pt-20 pb-10">
      <div className="container-grid">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,1.5fr)_minmax(0,2fr)]">
          <div>
            <div className="flex items-center gap-2.5 font-mono text-[12px] uppercase tracking-[0.22em] text-bone-0">
              <span className="grid h-3 w-3 place-items-center">
                <span className="h-2 w-2 bg-brick" />
              </span>
              FlowDesk
            </div>
            <p className="mt-6 max-w-md text-[14px] leading-relaxed text-bone-2">
              {t(lang, copy.footer.tagline)}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-8 md:grid-cols-3">
            {copy.footer.cols.map((col) => (
              <div key={col.title.en}>
                <div className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-bone-3">
                  {t(lang, col.title)}
                </div>
                <ul className="mt-5 space-y-2.5">
                  {col.links.map((l) => (
                    <li key={l.label.en}>
                      <a
                        href={l.href}
                        className="font-mono text-[12px] uppercase tracking-[0.18em] text-bone-1 transition-colors hover:text-brick"
                      >
                        {t(lang, l.label)}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-16 flex flex-col items-start justify-between gap-3 border-t border-[color:var(--hairline)] pt-6 font-mono text-[11px] uppercase tracking-[0.18em] text-bone-3 md:flex-row md:items-center">
          <span>{t(lang, copy.footer.legal)}</span>
          <span>v0.4 · Closed beta</span>
        </div>
      </div>
    </footer>
  );
}
