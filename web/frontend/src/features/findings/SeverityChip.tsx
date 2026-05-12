// SeverityChip — small colored badge for the closed severity enum.
//
// Color mapping picks oklch values so the chips stay readable in both
// light and dark mode (we still need a dark-mode pass in v1, but oklch
// at L=0.55–0.65 reads well on either background).

import styles from "./SeverityChip.module.css";

import type { Severity } from "./types";

interface Props {
  severity: Severity;
  /** Compact = 12px, default = 13px font. Useful in dense table rows. */
  compact?: boolean;
}

const SEVERITY_CLASS: Record<Severity, string> = {
  Critical: styles.critical,
  High: styles.high,
  Medium: styles.medium,
  Low: styles.low,
  Informational: styles.info,
};

export function SeverityChip({ severity, compact = false }: Props) {
  const cls = [
    styles.chip,
    SEVERITY_CLASS[severity],
    compact ? styles.compact : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={cls} title={severity} aria-label={`severity: ${severity}`}>
      {severity}
    </span>
  );
}
