"use client";

/**
 * Tiny i18n — English primary, Indonesian alternate.
 * Technical terms (orderflow, gamma, dealer, walls, IV, skew, snapshot, DTE, etc.)
 * stay in English in both locales. Per owner direction:
 * "kalau orderflow ya bilang orderflow jangan bilang aliran penjualan".
 *
 * Usage:
 *   import { useLang, t } from "@/lib/i18n";
 *   const lang = useLang();
 *   <h1>{t(lang, copy.hero.headline)}</h1>
 */

import { createContext, useContext, useState, useEffect, useCallback } from "react";

export type Lang = "en" | "id";

export type TString = { en: string; id: string };

export function t(lang: Lang, s: TString): string {
  return s[lang] ?? s.en;
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void };
const LangContext = createContext<Ctx>({ lang: "en", setLang: () => {} });

const STORAGE_KEY = "flowdesk:lang";

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Lang | null;
      if (saved === "en" || saved === "id") setLangState(saved);
    } catch {}
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {}
  }, []);

  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>;
}

export function useLang(): Lang {
  return useContext(LangContext).lang;
}

export function useSetLang(): (l: Lang) => void {
  return useContext(LangContext).setLang;
}
