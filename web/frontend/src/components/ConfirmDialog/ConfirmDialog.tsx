// <ConfirmDialog>
//
// Generic confirmation modal used by Slice S1 (Fork) and reused by Slice
// D2 (Cancel / Re-run). Lives under `components/` (not `features/`) so
// every slice can lift it without taking a feature dependency.
//
// A11y contract:
//   * role="dialog" + aria-modal="true" + aria-labelledby on the title
//   * ESC key closes via `onCancel`
//   * Tab key is trapped inside the dialog (focusable elements cycle)
//   * Focus is moved to the first focusable element on open, and restored
//     to whichever element was `document.activeElement` when the dialog
//     opened on close
//
// Visual:
//   * Fullscreen translucent backdrop, centred card
//   * `destructive=true` turns the confirm button red (oklch(0.55 0.20 30))
//   * Respects `prefers-reduced-motion: reduce` (transition removed via CSS)

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

import styles from "./ConfirmDialog.module.css";

export interface ConfirmDialogProps {
  /** Whether the dialog is currently visible. */
  open: boolean;
  /** Heading text (also used as aria-labelledby target). */
  title: string;
  /** Optional supporting paragraph below the title. */
  description?: string;
  /** Override for the confirm button label. Defaults to `t("common.confirm")`. */
  confirmLabel?: string;
  /** Override for the cancel button label. Defaults to `t("common.cancel")`. */
  cancelLabel?: string;
  /** Invoked when the user clicks the confirm button. */
  onConfirm: () => void;
  /** Invoked on cancel button click, backdrop click, or ESC keypress. */
  onCancel: () => void;
  /**
   * When true the confirm button uses the destructive red treatment.
   * Defaults to false — Fork is approve-emphasis, not destructive.
   */
  destructive?: boolean;
}

// CSS selector for elements we want to include in the focus trap.
const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => !el.hasAttribute("disabled"));
}

export function ConfirmDialog(props: ConfirmDialogProps): ReactElement | null {
  const {
    open,
    title,
    description,
    confirmLabel,
    cancelLabel,
    onConfirm,
    onCancel,
    destructive = false,
  } = props;

  const t = useT();
  const titleId = useId();
  const descId = useId();

  // The card element. Used to scope the focus trap so Tab cannot leak to
  // the backdrop or the underlying page.
  const cardRef = useRef<HTMLDivElement | null>(null);
  // Element that had focus before the dialog opened. We restore focus
  // here on close so keyboard users do not lose their place.
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // On open: snapshot the active element, then move focus into the card.
  // On close: restore focus to whatever had it pre-open.
  useEffect(() => {
    if (!open) return;

    previouslyFocused.current =
      (document.activeElement as HTMLElement | null) ?? null;

    // Defer focus move to the next microtask so the card has mounted.
    const raf = requestAnimationFrame(() => {
      const card = cardRef.current;
      if (!card) return;
      const focusables = getFocusable(card);
      // Prefer the confirm/cancel buttons — both live in the footer — over
      // the heading. We do not want the user to land on a non-actionable
      // element by default.
      const first = focusables[0] ?? card;
      first.focus();
    });

    return () => {
      cancelAnimationFrame(raf);
      // Restore focus only if the previously focused element is still
      // attached. If a parent re-render removed it the browser will
      // gracefully fall back to <body>.
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
        onCancel();
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

      // Cycle Tab / Shift+Tab inside the dialog. Without this the focus
      // can escape into the underlying SettingsPage which we have not
      // hidden via `inert` (broad support is still missing on Safari).
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
    [onCancel],
  );

  const handleBackdropClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      // Only react to clicks on the backdrop itself, not bubbles from the
      // card. Without this check, dragging a selection inside the card and
      // releasing the mouse on the backdrop would dismiss the dialog.
      if (event.target === event.currentTarget) {
        onCancel();
      }
    },
    [onCancel],
  );

  if (!open) return null;

  const resolvedConfirmLabel = confirmLabel ?? t("common.confirm");
  const resolvedCancelLabel = cancelLabel ?? t("common.cancel");

  const confirmClass = destructive
    ? `${styles.button} ${styles.buttonDestructive}`
    : `${styles.button} ${styles.buttonPrimary}`;

  return (
    <div
      className={styles.backdrop}
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      data-testid="confirm-dialog-backdrop"
    >
      <div
        ref={cardRef}
        className={styles.card}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        data-testid="confirm-dialog"
      >
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        {description ? (
          <p id={descId} className={styles.description}>
            {description}
          </p>
        ) : null}
        <div className={styles.footer}>
          <button
            type="button"
            className={`${styles.button} ${styles.buttonGhost}`}
            onClick={onCancel}
            data-testid="confirm-dialog-cancel"
          >
            {resolvedCancelLabel}
          </button>
          <button
            type="button"
            className={confirmClass}
            onClick={onConfirm}
            data-testid="confirm-dialog-confirm"
          >
            {resolvedConfirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmDialog;
