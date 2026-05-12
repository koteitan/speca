// Thin typed wrapper around react-i18next.
//
// In v1 we keep the key type as plain `string` to avoid coupling every
// slice to a generated `Resources` interface. In v2, when the key
// surface stabilizes, this is the single chokepoint we will tighten
// (replace the `TFunction` re-export with a typed variant).

import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import i18next, { SUPPORTED_LANGS } from "./index";

export type Lang = (typeof SUPPORTED_LANGS)[number];

/**
 * Convenience hook that returns just the `t` function.
 *
 * Equivalent to `useTranslation().t` for the `common` namespace.
 */
export function useT(): TFunction {
  return useTranslation().t;
}

/**
 * Current resolved language (region-stripped). Falls back to `ja` if
 * i18next has not yet settled on a language (should not happen after
 * `init` resolves, but the type system does not know that).
 */
export function getCurrentLang(): Lang {
  const raw = i18next.resolvedLanguage ?? i18next.language ?? "ja";
  const base = raw.split("-")[0];
  return (SUPPORTED_LANGS as readonly string[]).includes(base)
    ? (base as Lang)
    : "ja";
}

/**
 * Change the active language. Persists to localStorage via the
 * detector's `caches` config in `./index.ts`.
 */
export function setLang(lang: Lang): Promise<TFunction> {
  return i18next.changeLanguage(lang);
}
