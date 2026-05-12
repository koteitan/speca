// Two-button segmented language toggle (EN / JA).
//
// - `compact` shrinks padding/font for placement inside Header next
//   to the Settings gear. Standalone usage (e.g. inside a future
//   Settings page) can drop the prop for the larger variant.
// - Active language is communicated via `aria-pressed="true"` so
//   screen readers can announce the current selection without us
//   inventing custom semantics.
// - `<html lang>` is kept in sync centrally inside `src/i18n/index.ts`
//   via `i18next.on("languageChanged", ...)`, so this component only
//   needs to call `setLang`.

import { useTranslation } from "react-i18next";

import { getCurrentLang, setLang, type Lang } from "../../i18n/useT";
import styles from "./LanguageToggle.module.css";

export interface LanguageToggleProps {
  /** Use the compact (header) styling. */
  compact?: boolean;
}

const ORDER: ReadonlyArray<{ lang: Lang; label: string; titleKey: string }> = [
  { lang: "en", label: "EN", titleKey: "language.switch_to_en" },
  { lang: "ja", label: "JA", titleKey: "language.switch_to_ja" },
];

export function LanguageToggle({ compact = false }: LanguageToggleProps) {
  const { t, i18n } = useTranslation();
  // Subscribe to language changes via `i18n.resolvedLanguage` so the
  // active highlight re-renders when the user clicks the other button.
  // `i18n.resolvedLanguage` is the post-`load: 'languageOnly'` value.
  const current: Lang =
    (i18n.resolvedLanguage as Lang | undefined) ?? getCurrentLang();

  return (
    <div
      className={[styles.group, compact ? styles.compact : ""]
        .filter(Boolean)
        .join(" ")}
      role="group"
      aria-label={t("language.name")}
    >
      {ORDER.map(({ lang, label, titleKey }) => {
        const isActive = current === lang;
        return (
          <button
            key={lang}
            type="button"
            className={
              isActive ? `${styles.button} ${styles.buttonActive}` : styles.button
            }
            aria-pressed={isActive}
            title={t(titleKey)}
            onClick={() => {
              if (!isActive) {
                void setLang(lang);
              }
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export default LanguageToggle;
