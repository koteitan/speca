// ErrorModal — uniform error surface for the 7 §10.4 failure cases.
//
// Used by NewRunForm + WizardPage (and any other surface that needs to
// report a structured backend failure modally rather than inline). For
// known error codes the modal renders a title + body + suggested
// recovery action; for unknown codes it surfaces the raw envelope so
// the operator has something to copy/paste.
//
// A11y: role="dialog", aria-modal, focus trap, ESC to close — same
// pattern as ConfirmDialog and BudgetCapModal.

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type MouseEvent,
} from "react";

import { useT } from "@/i18n/useT";
import type { ErrorEnvelope } from "@/lib/errorEnvelope";

import styles from "./ErrorModal.module.css";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface ErrorModalProps {
  open: boolean;
  envelope: ErrorEnvelope | null;
  /** Optional retry handler. Shows a "Retry" button when provided. */
  onRetry?: () => void;
  onClose: () => void;
}

export function ErrorModal({
  open,
  envelope,
  onRetry,
  onClose,
}: ErrorModalProps) {
  const t = useT();
  const titleId = useId();
  const descId = useId();
  const cardRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => {
      const card = cardRef.current;
      if (!card) return;
      const focusables = Array.from(card.querySelectorAll<HTMLElement>(FOCUSABLE));
      (focusables[0] ?? card).focus();
    });
    return () => cancelAnimationFrame(id);
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
      const focusables = Array.from(card.querySelectorAll<HTMLElement>(FOCUSABLE));
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
      } else if (active === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  const handleBackdropClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) onClose();
    },
    [onClose],
  );

  if (!open || !envelope) return null;

  const i18nKey = envelope.isKnown && envelope.code ? envelope.code : "unknown";
  const title = t(`errors.${i18nKey}.title`);
  const message = t(`errors.${i18nKey}.message`);
  const action = t(`errors.${i18nKey}.action`);

  return (
    <div
      className={styles.backdrop}
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      data-testid="error-modal-backdrop"
    >
      <div
        ref={cardRef}
        className={styles.card}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        data-testid="error-modal"
      >
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        <p id={descId} className={styles.description}>
          {message}
        </p>
        {action ? <p className={styles.action}>{action}</p> : null}
        <details className={styles.raw}>
          <summary>{t("errors.show_raw")}</summary>
          <pre className={styles.rawBody}>
            {envelope.code ? `[${envelope.code}]\n` : ""}
            {envelope.message}
            {envelope.status ? `\n(HTTP ${envelope.status})` : ""}
          </pre>
        </details>
        <div className={styles.footer}>
          {onRetry ? (
            <button
              type="button"
              className={`${styles.button} ${styles.buttonPrimary}`}
              onClick={onRetry}
              data-testid="error-modal-retry"
            >
              {t("common.retry")}
            </button>
          ) : null}
          <button
            type="button"
            className={`${styles.button} ${styles.buttonGhost}`}
            onClick={onClose}
            data-testid="error-modal-close"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ErrorModal;
