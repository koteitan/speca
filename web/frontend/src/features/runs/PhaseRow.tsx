import { useState } from "react";

import { OpenInVSCode } from "@/components/OpenInVSCode";
import { useT } from "@/i18n/useT";

import { LogTail } from "./LogTail";
import { formatPhaseLabel } from "./phaseDisplayNames";
import { StatusIcon } from "./StatusIcon";
import type { PhaseRow as PhaseRowType } from "./types";
import styles from "./PhaseRow.module.css";

/**
 * Format a duration in seconds as a compact "m s" string. Falls back to
 * an em-dash when the underlying value is `null` (i.e. the phase never
 * started, so no duration is available).
 */
function formatDuration(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) {
    return "—"; // em dash
  }
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)}ms`;
  }
  if (seconds < 60) {
    return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds - minutes * 60);
  return `${minutes}m ${rest}s`;
}

export interface PhaseRowProps {
  phase: PhaseRowType;
  /**
   * Absolute path to the run's log folder. Slice G threads this through
   * from <RunDetailPage> so the row can mount a "log フォルダを VSCode で開く"
   * menuitem when expanded. May be `null` while the integrations/paths
   * query is still loading; the row simply omits the link in that case.
   */
  logsPath?: string | null;
  /**
   * Slice D1 — live log lines accumulated by `useRunStream` for this
   * phase. Undefined means the run is not currently being streamed (or
   * no lines have arrived yet); we render the LogTail with an empty
   * buffer + "no log lines yet" placeholder in that case, but only when
   * the run is live (`isLive`).
   */
  logs?: string[];
  /**
   * True while a WebSocket subscription is active for the parent run.
   * When false we keep the v0 "logs stream in v1" placeholder so the
   * UI for already-finished runs is unchanged.
   */
  isLive?: boolean;
}

/**
 * One collapsible row in the Run Detail page.
 *
 * The expanded body carries a Slice-G `<OpenInVSCode>` menuitem pointing
 * at the run's log folder; the live log stream itself lands in v1. The
 * `data-testid="phase-row-<id>"` attribute is the integration point.
 */
export function PhaseRow({ phase, logsPath, logs, isLive }: PhaseRowProps) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const label = formatPhaseLabel(phase.phase_id);

  return (
    <div data-testid={`phase-row-${phase.phase_id}`}>
      <button
        type="button"
        className={styles.row}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <StatusIcon status={phase.status} />
        <span className={styles.label}>{label}</span>
        <span className={styles.duration}>
          {formatDuration(phase.duration_seconds)}
        </span>
        <span
          className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`}
          aria-hidden="true"
        >
          {"▶"}
        </span>
      </button>
      {open ? (
        <div
          className={styles.detail}
          role="region"
          aria-label={t("runs.phase_row.details_aria", { label })}
        >
          {isLive ? (
            <LogTail phaseId={phase.phase_id} lines={logs ?? []} />
          ) : (
            <em>{t("runs.phase_row.no_log_preview")}</em>
          )}
          {logsPath ? (
            <div className={styles.detailActions}>
              <OpenInVSCode
                path={logsPath}
                label={t("runs.phase_row.open_log_folder")}
                variant="menuitem"
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
