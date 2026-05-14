// CLI spec §5.3.3 — budget cap-bump modal.
//
// Mirrors the CLI's "halt at 100% and prompt to raise the cap" affordance.
// The supervisor does not yet enforce caps (see the TODO in
// run_supervisor.py), so for v0 the modal simply round-trips through the
// state.json cap field — it is functional UX but advisory until the
// orchestrator slice that wires enforcement lands.
//
// A11y: same patterns as ConfirmDialog (role=dialog, aria-modal, focus
// trap, ESC closes). The input is the initial focus target so users can
// type a new cap immediately. The "Clear cap" footer link is a tertiary
// affordance — useful when reverting after experimentation.

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";

import { useT } from "@/i18n/useT";

import styles from "./BudgetCapModal.module.css";

export interface BudgetCapModalProps {
  open: boolean;
  /** USD spent so far — only used to compute the "raise to ≥ spent" hint. */
  spent: number;
  /** Current cap (USD) or null when no cap is configured. */
  currentCap: number | null;
  /** Confirm callback — null clears the cap, number sets / raises it. */
  onConfirm: (newCap: number | null) => void;
  onCancel: () => void;
  /** Disable buttons while the network mutation is in flight. */
  busy?: boolean;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function BudgetCapModal({
  open,
  spent,
  currentCap,
  onConfirm,
  onCancel,
  busy = false,
}: BudgetCapModalProps) {
  const t = useT();
  const titleId = useId();
  const descId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);

  // Pre-fill with a sensible default: 2× the current cap (or 2× spent
  // when no cap is set) so the user only has to press Enter to ack the
  // suggestion. They can still type any other value.
  const suggested = (() => {
    if (currentCap !== null && Number.isFinite(currentCap) && currentCap > 0) {
      return (currentCap * 2).toFixed(2);
    }
    if (Number.isFinite(spent) && spent > 0) {
      return (Math.max(spent, 0) * 2).toFixed(2);
    }
    return "5.00";
  })();
  const [value, setValue] = useState(suggested);

  // Re-seed the input whenever the modal opens (or the run's cap changes
  // out from under us mid-session via a different surface).
  useEffect(() => {
    if (open) setValue(suggested);
  }, [open, suggested]);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
    return () => cancelAnimationFrame(id);
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
    [onCancel],
  );

  const handleBackdropClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) onCancel();
    },
    [onCancel],
  );

  if (!open) return null;

  const parsed = Number.parseFloat(value);
  const isValid = Number.isFinite(parsed) && parsed > 0;
  const insufficient = isValid && spent > 0 && parsed < spent;

  return (
    <div
      className={styles.backdrop}
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      data-testid="budget-cap-modal-backdrop"
    >
      <div
        ref={cardRef}
        className={styles.card}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        data-testid="budget-cap-modal"
      >
        <h2 id={titleId} className={styles.title}>
          {t("runs.detail.budget_cap.title")}
        </h2>
        <p id={descId} className={styles.description}>
          {t("runs.detail.budget_cap.description", {
            spent: spent.toFixed(2),
            cap:
              currentCap !== null && Number.isFinite(currentCap)
                ? currentCap.toFixed(2)
                : t("common.none"),
          })}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (busy || !isValid) return;
            onConfirm(parsed);
          }}
        >
          <label className={styles.label} htmlFor={`${titleId}-input`}>
            {t("runs.detail.budget_cap.input_label")}
          </label>
          <div className={styles.inputRow}>
            <span className={styles.inputPrefix} aria-hidden="true">$</span>
            <input
              ref={inputRef}
              id={`${titleId}-input`}
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className={styles.input}
              data-testid="budget-cap-input"
              disabled={busy}
            />
          </div>
          {insufficient ? (
            <p className={styles.warn} role="alert">
              {t("runs.detail.budget_cap.warn_below_spent")}
            </p>
          ) : null}
          <div className={styles.footer}>
            <button
              type="button"
              className={`${styles.button} ${styles.buttonGhost}`}
              onClick={() => onConfirm(null)}
              disabled={busy || currentCap === null}
              data-testid="budget-cap-clear"
            >
              {t("runs.detail.budget_cap.clear")}
            </button>
            <span className={styles.spacer} />
            <button
              type="button"
              className={`${styles.button} ${styles.buttonGhost}`}
              onClick={onCancel}
              disabled={busy}
              data-testid="budget-cap-cancel"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              className={`${styles.button} ${styles.buttonPrimary}`}
              disabled={busy || !isValid}
              data-testid="budget-cap-confirm"
            >
              {busy
                ? t("runs.detail.budget_cap.saving")
                : t("runs.detail.budget_cap.confirm")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default BudgetCapModal;
