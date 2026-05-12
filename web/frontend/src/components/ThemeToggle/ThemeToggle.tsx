// 3-state theme toggle: Light / Dark / System.
//
// Matches `<LanguageToggle/>`'s segmented look (Nyx tokens, focus-visible
// 2px outline) so the Header has a consistent control language.

import { useT } from "@/i18n/useT";
import { useTheme, type ThemeMode } from "@/store/themeSlice";

import styles from "./ThemeToggle.module.css";

interface ThemeToggleProps {
  /** Tighter version for the Header tools row. */
  compact?: boolean;
}

const MODES: ThemeMode[] = ["light", "dark", "system"];

const LABEL_KEY: Record<ThemeMode, string> = {
  light: "theme.light",
  dark: "theme.dark",
  system: "theme.system",
};

export default function ThemeToggle({ compact = false }: ThemeToggleProps) {
  const mode = useTheme((s) => s.mode);
  const setMode = useTheme((s) => s.setMode);
  const t = useT();

  return (
    <div
      role="group"
      aria-label={t("theme.label")}
      className={`${styles.group} ${compact ? styles.compact : ""}`}
      data-testid="theme-toggle"
    >
      {MODES.map((m) => (
        <button
          key={m}
          type="button"
          className={`${styles.button} ${
            mode === m ? styles.buttonActive : ""
          }`}
          onClick={() => setMode(m)}
          aria-pressed={mode === m}
          data-testid={`theme-toggle-${m}`}
        >
          {t(LABEL_KEY[m])}
        </button>
      ))}
    </div>
  );
}
