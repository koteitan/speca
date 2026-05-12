import type { PhaseStatus, RunStatus } from "./types";
import styles from "./StatusIcon.module.css";

// Glyph table: keep the keys in sync with `PhaseStatus | RunStatus`.
// We use literal text glyphs (not SVG) so the icon inherits font sizing
// from its row and stays crisp at any zoom level.
const GLYPHS: Record<PhaseStatus | RunStatus, string> = {
  ok: "✓", // check mark
  failed: "✗", // ballot X
  running: "•", // bullet
  cancelled: "↻", // clockwise open circle arrow
  pending: "○", // white circle
  skipped: "⊘", // circled division slash
};

// Accessible label for screen readers. Matches the glyph meaning rather
// than the literal char so the SR reads "success" instead of "check mark".
const A11Y_LABEL: Record<PhaseStatus | RunStatus, string> = {
  ok: "success",
  failed: "failed",
  running: "running",
  cancelled: "cancelled",
  pending: "pending",
  skipped: "skipped",
};

export interface StatusIconProps {
  status: PhaseStatus | RunStatus;
  /** Optional extra class for layout (size, margin, ...). */
  className?: string;
}

/**
 * GitHub-Actions-style status glyph.
 *
 * Colors come from CSS Modules (`StatusIcon.module.css`) so this
 * component stays themeable without prop drilling.
 *
 * TODO(v1): promote to `components/` once a second slice needs it.
 */
export function StatusIcon({ status, className }: StatusIconProps) {
  const cls = [styles.icon, styles[status], className]
    .filter(Boolean)
    .join(" ");
  return (
    <span
      className={cls}
      role="img"
      aria-label={A11Y_LABEL[status]}
      data-testid={`status-icon-${status}`}
    >
      {GLYPHS[status]}
    </span>
  );
}
