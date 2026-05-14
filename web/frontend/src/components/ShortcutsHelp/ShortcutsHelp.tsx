// <ShortcutsHelp>
//
// Keyboard-shortcuts help modal — opened by pressing `?`.
//
// Reuses the ConfirmDialog visual/a11y pattern (translucent backdrop,
// centred card, focus trap, Esc-to-close, prefers-reduced-motion respect).
// The only structural difference is the body: a two-section table of
// shortcuts ("Global" / "Findings") instead of confirm/cancel buttons.
// A single "Close" button lives in the footer.

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type MouseEvent,
  type ReactElement,
} from "react";

import { useT } from "@/i18n/useT";

import styles from "./ShortcutsHelp.module.css";

export interface ShortcutsHelpProps {
  open: boolean;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => !el.hasAttribute("disabled"));
}

interface ShortcutRow {
  /** Key combination, e.g. `?`, `g r`, `Esc`. */
  keys: string;
  /** Localised description. */
  description: string;
}

export function ShortcutsHelp(props: ShortcutsHelpProps): ReactElement | null {
  const { open, onClose } = props;
  const t = useT();
  const titleId = useId();

  const cardRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // Snapshot the previously-focused element on open; move focus into the
  // dialog; restore on close. Mirrors ConfirmDialog.
  useEffect(() => {
    if (!open) return;

    previouslyFocused.current =
      (document.activeElement as HTMLElement | null) ?? null;

    const raf = requestAnimationFrame(() => {
      const card = cardRef.current;
      if (!card) return;
      const focusables = getFocusable(card);
      const first = focusables[0] ?? card;
      first.focus();
    });

    return () => {
      cancelAnimationFrame(raf);
      const prev = previouslyFocused.current;
      if (prev && document.contains(prev)) {
        prev.focus();
      }
      previouslyFocused.current = null;
    };
  }, [open]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const card = cardRef.current;
      if (!card) return;
      const focusables = getFocusable(card);
      if (focusables.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (event.shiftKey) {
        if (active === first || !card.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else {
        if (active === last) {
          event.preventDefault();
          first.focus();
        }
      }
    },
    [onClose],
  );

  const handleBackdropClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) {
        onClose();
      }
    },
    [onClose],
  );

  if (!open) return null;

  const globalRows: ShortcutRow[] = [
    { keys: "?", description: t("shortcuts.k_question") },
    { keys: "Esc", description: t("shortcuts.k_esc") },
    { keys: "c", description: t("shortcuts.k_c") },
    { keys: "g r", description: t("shortcuts.k_g_r") },
    { keys: "g s", description: t("shortcuts.k_g_s") },
    { keys: "g d", description: t("shortcuts.k_g_d") },
  ];
  const findingsRows: ShortcutRow[] = [
    { keys: "/", description: t("shortcuts.k_slash") },
    { keys: "j", description: t("shortcuts.k_j") },
    { keys: "k", description: t("shortcuts.k_k") },
  ];

  return (
    <div
      className={styles.backdrop}
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      data-testid="shortcuts-help-backdrop"
    >
      <div
        ref={cardRef}
        className={styles.card}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid="shortcuts-help"
      >
        <h2 id={titleId} className={styles.title}>
          {t("shortcuts.help_title")}
        </h2>
        <ShortcutSection
          heading={t("shortcuts.global_section")}
          rows={globalRows}
        />
        <ShortcutSection
          heading={t("shortcuts.findings_section")}
          rows={findingsRows}
        />
        <div className={styles.footer}>
          <button
            type="button"
            className={`${styles.button} ${styles.buttonPrimary}`}
            onClick={onClose}
            data-testid="shortcuts-help-close"
          >
            {t("shortcuts.help_close")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface ShortcutSectionProps {
  heading: string;
  rows: ShortcutRow[];
}

function ShortcutSection({ heading, rows }: ShortcutSectionProps): ReactElement {
  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{heading}</h3>
      <table className={styles.table}>
        <tbody>
          {rows.map((row) => (
            <tr key={row.keys}>
              <td className={styles.keyCell}>
                <kbd className={styles.kbd}>{row.keys}</kbd>
              </td>
              <td className={styles.descCell}>{row.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default ShortcutsHelp;
