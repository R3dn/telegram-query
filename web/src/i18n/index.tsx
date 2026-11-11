/** UI localization: English (default) and Arabic with true RTL.
 *
 *  Architecture:
 *  - Per-view string files under i18n/en/* and i18n/ar/* (flat
 *    dot-namespaced keys). One file per view per language: parallel
 *    work on different views never edits the same file.
 *  - `t("key", vars?)` resolves the active language, falls back to
 *    English, then to the key itself (a missing translation is
 *    visible, never an empty string).
 *  - Switching language updates <html lang> and <html dir>, so the
 *    browser, focus order, scrollbars, and logical CSS all flip
 *    correctly, plus the `rtl` class for the few physical CSS rules.
 *  - The choice persists in localStorage ("tgq-lang"); index.html
 *    applies it before first paint (no flash).
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Dict, Lang } from "./types";

import * as shellEn from "./en/shell";
import * as browseEn from "./en/browse";
import * as discoverEn from "./en/discover";
import * as entitiesEn from "./en/entities";
import * as bookmarksEn from "./en/bookmarks";
import * as dealsEn from "./en/deals";
import * as decisionsEn from "./en/decisions";
import * as researchEn from "./en/research";
import * as watchEn from "./en/watch";
import * as digestsEn from "./en/digests";
import * as faqsEn from "./en/faqs";
import * as onboardingEn from "./en/onboarding";
import * as systemEn from "./en/system";
import * as panelsEn from "./en/panels";

import * as shellAr from "./ar/shell";
import * as browseAr from "./ar/browse";
import * as discoverAr from "./ar/discover";
import * as entitiesAr from "./ar/entities";
import * as bookmarksAr from "./ar/bookmarks";
import * as dealsAr from "./ar/deals";
import * as decisionsAr from "./ar/decisions";
import * as researchAr from "./ar/research";
import * as watchAr from "./ar/watch";
import * as digestsAr from "./ar/digests";
import * as faqsAr from "./ar/faqs";
import * as onboardingAr from "./ar/onboarding";
import * as systemAr from "./ar/system";
import * as panelsAr from "./ar/panels";

export type { Lang } from "./types";
export type { Dict } from "./types";

const EN: Dict = {
  ...shellEn.dict,
  ...browseEn.dict,
  ...discoverEn.dict,
  ...entitiesEn.dict,
  ...bookmarksEn.dict,
  ...dealsEn.dict,
  ...decisionsEn.dict,
  ...researchEn.dict,
  ...watchEn.dict,
  ...digestsEn.dict,
  ...faqsEn.dict,
  ...onboardingEn.dict,
  ...systemEn.dict,
  ...panelsEn.dict,
};

const AR: Dict = {
  ...shellAr.dict,
  ...browseAr.dict,
  ...discoverAr.dict,
  ...entitiesAr.dict,
  ...bookmarksAr.dict,
  ...dealsAr.dict,
  ...decisionsAr.dict,
  ...researchAr.dict,
  ...watchAr.dict,
  ...digestsAr.dict,
  ...faqsAr.dict,
  ...onboardingAr.dict,
  ...systemAr.dict,
  ...panelsAr.dict,
};

export function readStoredLang(): Lang {
  const stored = localStorage.getItem("tgq-lang");
  if (stored === "ar" || stored === "en") return stored;
  return navigator.language?.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function applyLangToDocument(lang: Lang): void {
  const el = document.documentElement;
  el.lang = lang;
  el.dir = lang === "ar" ? "rtl" : "ltr";
  el.classList.toggle("rtl", lang === "ar");
}

interface LangApi {
  lang: Lang;
  isRTL: boolean;
  dir: "ltr" | "rtl";
  setLang: (l: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const Ctx = createContext<LangApi | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStoredLang);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    localStorage.setItem("tgq-lang", l);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      const table = lang === "ar" ? AR : EN;
      let s = table[key] ?? EN[key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          s = s.replaceAll(`{${k}}`, String(v));
        }
      }
      return s;
    },
    [lang],
  );

  const api = useMemo<LangApi>(
    () => ({
      lang,
      isRTL: lang === "ar",
      dir: lang === "ar" ? "rtl" : "ltr",
      setLang,
      t,
    }),
    [lang, setLang, t],
  );

  // Keep <html> in sync on in-session switches (index.html does the
  // initial pre-paint application to avoid a direction flash).
  applyLangToDocument(lang);

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useLang(): LangApi {
  const api = useContext(Ctx);
  if (!api) throw new Error("useLang outside <LangProvider>");
  return api;
}

/** User-authored content (message text, titles, notes) renders with
 *  `dir="auto"` so mixed Arabic/Latin content flows correctly
 *  regardless of the UI language. */
export const AUTO_DIR = { dir: "auto" } as const;
