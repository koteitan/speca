// "Saved targets" entry of the Project Picker (Slice R1, panel A).
//
// Reads from the existing `useSavedTargets()` hook (Slice F). On click,
// the row applies itself to the shared `useNewRunDraft` store and
// navigates to the R2 review path. R2 itself is not in this slice — the
// navigation lands on a 404 until R2 merges, which is acceptable for
// smoke testing the picker contract.

import { useNavigate } from "react-router-dom";

import { Spinner } from "@/components/Spinner/Spinner";
import { EmptyState } from "@/components/EmptyState/EmptyState";
import { useT } from "@/i18n/useT";
import { useNewRunDraft } from "@/store/newRunDraftSlice";

import type { SavedTarget } from "./types";
import { useSavedTargets } from "./useSavedTargets";
import styles from "./SavedTargetsList.module.css";

/** Format an ISO string as a short relative time like "5m ago". */
function formatRelative(iso: string | null, neverLabel: string): string {
  if (!iso) return neverLabel;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return neverLabel;
  const delta = Math.max(0, Date.now() - t);
  const seconds = Math.floor(delta / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export interface SavedTargetsListProps {
  /** R2 review path. Hard-coded as `/runs/new/review` in the page —
   *  parameterised here for testability. */
  reviewPath: string;
}

export function SavedTargetsList({ reviewPath }: SavedTargetsListProps) {
  const t = useT();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useSavedTargets();

  const applyFromSaved = useNewRunDraft((s) => s.applyFromSaved);

  const onPick = (target: SavedTarget) => {
    applyFromSaved(target);
    navigate(reviewPath);
  };

  if (isLoading) {
    return (
      <div className={styles.loading} role="status">
        <Spinner size="sm" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className={styles.error} role="alert">
        {String((error as Error)?.message ?? "unknown error")}
      </div>
    );
  }

  const entries = data ?? [];
  if (entries.length === 0) {
    return <EmptyState title={t("picker.saved.empty")} />;
  }

  const neverLabel = t("picker.saved.last_run_never");
  const demoBadge = t("picker.saved.demo_badge");

  return (
    <ul className={styles.list} aria-label={t("picker.page.saved")}>
      {entries.map((target) => {
        const key = `${target.target_repo}|${target.source}|${
          target.target_ref ?? ""
        }`;
        return (
          <li key={key} className={styles.item}>
            <button
              type="button"
              className={styles.row}
              onClick={() => onPick(target)}
              data-testid={`saved-target-${target.target_repo}`}
            >
              <span className={styles.repo}>
                {target.target_repo}
                {target.source === "demo" ? (
                  <span className={styles.badge}>{demoBadge}</span>
                ) : null}
              </span>
              <span className={styles.meta}>
                {target.target_ref ? (
                  <span className={styles.ref}>{target.target_ref}</span>
                ) : null}
                {/* For demo seeds without history hide the timestamp
                 *  entirely — "never" would imply the user neglected to
                 *  run it, but the demo badge already explains the
                 *  state. Real history rows always carry a timestamp. */}
                {target.source === "demo" && !target.last_run_at ? (
                  <span className={styles.time}>
                    {t("picker.saved.demo_hint")}
                  </span>
                ) : (
                  <span className={styles.time}>
                    {formatRelative(
                      target.last_run_at
                        ? new Date(target.last_run_at).toISOString()
                        : null,
                      neverLabel,
                    )}
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default SavedTargetsList;
