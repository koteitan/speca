// <RerunDialog>
//
// Slice D2 — phase-picker dialog for `POST /api/runs/{run_id}/rerun`.
//
// Why not extend ConfirmDialog?
//   ConfirmDialog is intentionally text-only (title + description +
//   two buttons). The rerun flow needs an interactive checkbox list, so
//   wedging a `children` slot into ConfirmDialog would either widen its
//   API for everyone (Slice S1's Fork dialog stays text-only) or force
//   this dialog into a cramped layout. We re-implement the chrome here
//   with the same a11y contract:
//
//     * role="dialog" + aria-modal + aria-labelledby/describedby
//     * ESC key calls `onCancel`
//     * Tab is trapped inside the card (cycle through focusables)
//     * Focus moves to the first focusable on open; restored on close
//     * Respects prefers-reduced-motion via the CSS module
//
// Phase pre-selection rule:
//   `failed` and `cancelled` phases default to checked; everything else
//   (ok / pending / running / skipped) defaults to unchecked. The user
//   can toggle any phase. We do NOT filter out non-failed phases from
//   the list, because a user might legitimately want to re-run an `ok`
//   phase (e.g. after pulling a fix to its prompt template).
//
// Confirm is disabled when 0 boxes are checked — sending an empty
// `phases` array would 422 at the router boundary, and we want the
// "disable, don't pre-validate-and-toast" pattern that ConfirmDialog
// uses.

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
  type ReactElement,
} from "react";

import { useT } from "@/i18n/useT";

import { formatPhaseLabel } from "./phaseDisplayNames";
import type { PhaseRow, PhaseStatus } from "./types";
import styles from "./RerunDialog.module.css";

export interface RerunDialogProps {
  /** Whether the dialog is currently visible. */
  open: boolean;
  /** All phases for the run — drives the checkbox list. */
  phases: PhaseRow[];
  /** Invoked with the selected phase ids when the user clicks Confirm. */
  onConfirm: (selectedPhases: string[]) => void;
  /** Invoked on cancel button click, backdrop click, or ESC. */
  onCancel: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => !el.hasAttribute("disabled"));
}

/** Pre-select rule: failed + cancelled default to checked. */
function isDefaultChecked(status: PhaseStatus): boolean {
  return status === "failed" || status === "cancelled";
}

export function RerunDialog(props: RerunDialogProps): ReactElement | null {
  const { open, phases, onConfirm, onCancel } = props;
  const t = useT();
  const titleId = useId();
  const descId = useId();

  // Card element — scopes the focus trap so Tab cannot leak to the
  // underlying page.
  const cardRef = useRef<HTMLDivElement | null>(null);
  // Element that had focus before the dialog opened; restored on close.
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // Selected phase ids. Re-seed every time `open` flips to true so a
  // dialog reopened after a previous interaction reflects the current
  // run state (status may have moved on between opens via WS frames).
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    if (!open) return;
    const seed = new Set<string>();
    for (const phase of phases) {
      if (isDefaultChecked(phase.status)) {
        seed.add(phase.phase_id);
      }
    }
    setSelected(seed);
  }, [open, phases]);

  // Focus management: capture, move, restore.
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
      if (event.target === event.currentTarget) {
        onCancel();
      }
    },
    [onCancel],
  );

  // Derived: are there any failed/cancelled phases to suggest a default
  // selection from? Used to decide whether the "Select all failed"
  // shortcut is meaningful and to render the empty-state hint.
  const hasFailedOrCancelled = useMemo(
    () => phases.some((p) => isDefaultChecked(p.status)),
    [phases],
  );

  const toggle = useCallback((phaseId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(phaseId)) {
        next.delete(phaseId);
      } else {
        next.add(phaseId);
      }
      return next;
    });
  }, []);

  const handleSelectAllFailed = useCallback(() => {
    setSelected(() => {
      const next = new Set<string>();
      for (const phase of phases) {
        if (isDefaultChecked(phase.status)) {
          next.add(phase.phase_id);
        }
      }
      return next;
    });
  }, [phases]);

  const handleConfirm = useCallback(() => {
    if (selected.size === 0) return;
    // Stable order — keep the phase chain order so the orchestrator's
    // dependency resolver receives them in a natural sequence (it sorts
    // internally anyway, but a sorted payload makes server logs easier
    // to read).
    const ordered = phases
      .filter((p) => selected.has(p.phase_id))
      .map((p) => p.phase_id);
    onConfirm(ordered);
  }, [onConfirm, phases, selected]);

  if (!open) return null;

  const confirmDisabled = selected.size === 0;

  return (
    <div
      className={styles.backdrop}
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      data-testid="rerun-dialog-backdrop"
    >
      <div
        ref={cardRef}
        className={styles.card}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        data-testid="rerun-dialog"
      >
        <h2 id={titleId} className={styles.title}>
          {t("runs.detail.rerun.dialog_title")}
        </h2>
        <p id={descId} className={styles.description}>
          {t("runs.detail.rerun.dialog_description")}
        </p>

        {phases.length > 0 ? (
          <>
            <div className={styles.toolbar}>
              <button
                type="button"
                className={styles.toolbarButton}
                onClick={handleSelectAllFailed}
                disabled={!hasFailedOrCancelled}
                data-testid="rerun-dialog-select-all-failed"
              >
                {t("runs.detail.rerun.select_all_failed")}
              </button>
            </div>
            <ul className={styles.list} data-testid="rerun-dialog-phase-list">
              {phases.map((phase) => {
                const checked = selected.has(phase.phase_id);
                return (
                  <li key={phase.phase_id} className={styles.item}>
                    <label className={styles.itemLabel}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(phase.phase_id)}
                        data-testid={`rerun-dialog-phase-${phase.phase_id}`}
                      />
                      <span>{formatPhaseLabel(phase.phase_id)}</span>
                    </label>
                    <span className={styles.itemStatus}>{phase.status}</span>
                  </li>
                );
              })}
            </ul>
            {!hasFailedOrCancelled ? (
              <p className={styles.description}>
                {t("runs.detail.rerun.no_failed_phases")}
              </p>
            ) : null}
          </>
        ) : (
          <p className={styles.empty}>
            {t("runs.detail.rerun.no_failed_phases")}
          </p>
        )}

        <div className={styles.footer}>
          <button
            type="button"
            className={`${styles.button} ${styles.buttonGhost}`}
            onClick={onCancel}
            data-testid="rerun-dialog-cancel"
          >
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className={`${styles.button} ${styles.buttonPrimary}`}
            onClick={handleConfirm}
            disabled={confirmDisabled}
            data-testid="rerun-dialog-confirm"
          >
            {t("runs.detail.rerun.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default RerunDialog;
