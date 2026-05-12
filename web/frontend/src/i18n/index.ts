// i18next bootstrap for SPECA Web UI (Slice I1).
//
// Design notes:
//   - We bundle locale resources synchronously (no async fetch), so no
//     Suspense fallback is needed by consumers.
//   - Default UI language is Japanese: `fallbackLng: 'ja'`. If the user
//     has nothing persisted and the browser does not signal a language
//     we support, JA wins.
//   - Detection order is `localStorage → navigator → htmlTag`. The
//     localStorage key is unified as `speca.lang` so it cannot collide
//     with other apps on the same origin.
//   - `load: 'languageOnly'` strips region tags (e.g. `ja-JP` → `ja`,
//     `en-US` → `en`) before resource lookup.
//   - `supportedLngs: ['en','ja']` ensures unknown languages cannot
//     bleed into the selection; they will fall back to `ja`.
//   - `interpolation.escapeValue = false` because React already
//     escapes by default and double-escaping breaks Japanese punctuation.

import i18next from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import enCommon from "./locales/en/common.json";
import jaCommon from "./locales/ja/common.json";

export const SUPPORTED_LANGS = ["en", "ja"] as const;
export const LANG_STORAGE_KEY = "speca.lang";

void i18next
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "ja",
    defaultNS: "common",
    ns: ["common"],
    supportedLngs: [...SUPPORTED_LANGS],
    load: "languageOnly",
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator", "htmlTag"],
      lookupLocalStorage: LANG_STORAGE_KEY,
      caches: ["localStorage"],
    },
    resources: {
      en: { common: enCommon },
      ja: { common: jaCommon },
    },
  });

// Keep `<html lang>` in sync with the active language, both at boot and
// on every subsequent change. Slice I1 owns this side-effect so later
// slices do not need to wire it again.
const syncHtmlLang = (lang: string) => {
  if (typeof document !== "undefined") {
    document.documentElement.lang = lang;
  }
};

syncHtmlLang(i18next.resolvedLanguage ?? i18next.language ?? "ja");
i18next.on("languageChanged", (lang) => {
  syncHtmlLang(lang);
});

export default i18next;
