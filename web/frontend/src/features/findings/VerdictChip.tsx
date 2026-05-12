// VerdictChip — visual badge for the (possibly-open) verdict string.
//
// The closed set defined in `types.ts::KNOWN_VERDICTS` gets a hue-coded
// chip; anything else falls through to a neutral "unknown" style. We do
// NOT silently drop unknown verdicts — forks may emit custom verdicts
// and the user still wants to see them.

import styles from "./VerdictChip.module.css";

import { isKnownVerdict, type KnownVerdict } from "./types";

interface Props {
  verdict: string | null | undefined;
}

const VERDICT_CLASS: Record<KnownVerdict, string> = {
  CONFIRMED_VULNERABILITY: styles.confirmedVuln,
  CONFIRMED_POTENTIAL: styles.confirmedPotential,
  DISPUTED_FP: styles.disputedFp,
  DOWNGRADED: styles.downgraded,
  NEEDS_MANUAL_REVIEW: styles.needsReview,
  PASS_THROUGH: styles.passThrough,
};

const VERDICT_LABEL: Record<KnownVerdict, string> = {
  CONFIRMED_VULNERABILITY: "Confirmed vuln",
  CONFIRMED_POTENTIAL: "Confirmed potential",
  DISPUTED_FP: "Disputed FP",
  DOWNGRADED: "Downgraded",
  NEEDS_MANUAL_REVIEW: "Needs review",
  PASS_THROUGH: "Pass-through",
};

export function VerdictChip({ verdict }: Props) {
  if (!verdict) return <span className={styles.none}>—</span>;

  if (isKnownVerdict(verdict)) {
    return (
      <span
        className={`${styles.chip} ${VERDICT_CLASS[verdict]}`}
        title={verdict}
      >
        {VERDICT_LABEL[verdict]}
      </span>
    );
  }
  // Unknown verdict — show the raw value so a fork's custom label stays
  // visible. Neutral border so it doesn't mimic the known styles.
  return (
    <span className={`${styles.chip} ${styles.unknown}`} title={verdict}>
      {verdict}
    </span>
  );
}
