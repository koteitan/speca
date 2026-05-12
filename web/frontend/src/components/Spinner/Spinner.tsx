// Minimal token-driven spinner.
//
// Pure CSS animation (no SVG) so it tree-shakes to ~0 JS. Sized via the
// `size` prop which maps to a CSS variable on the wrapper — Nyx tokens
// stay the source of truth for color/border so light/dark mode just works.
//
// Used by AppShell as the Suspense fallback for the lazy ChatPanel and
// exported for any feature slice that needs a placeholder.
//
// The `label` prop is the SR-only accessible name. Callers that have
// access to a `useT()` `t` function should pass a translated string;
// when omitted, the spinner falls back to the localized "Loading…"
// string via the global i18next instance so the SR experience is never
// untranslated.

import i18next from "@/i18n";

import styles from "./Spinner.module.css";

export type SpinnerSize = "sm" | "md" | "lg";

export interface SpinnerProps {
  size?: SpinnerSize;
  /**
   * Accessible label read by screen readers. Defaults to a localized
   * "Loading…" string.
   */
  label?: string;
}

export function Spinner({ size = "md", label }: SpinnerProps) {
  const resolvedLabel = label ?? i18next.t("common.loading_short");
  return (
    <span
      className={styles.spinner}
      data-size={size}
      role="status"
      aria-live="polite"
    >
      <span className={styles.ring} aria-hidden="true" />
      <span className={styles.srOnly}>{resolvedLabel}</span>
    </span>
  );
}

export default Spinner;
