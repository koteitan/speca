// FilterBar — severity chips + verdict chips + phase toggle.
//
// State lives in the URL via `useSearchParams` so a finding list link can
// be bookmarked / shared with filters intact. The page itself reads the
// same searchParams to drive the query, so this component never has to
// "lift state up" — it just edits the URL.

import { useSearchParams } from "react-router-dom";

import styles from "./FilterBar.module.css";

import {
  KNOWN_VERDICTS,
  PHASES,
  SEVERITY_LEVELS,
  type KnownVerdict,
  type Phase,
  type Severity,
} from "./types";

const VERDICT_LABEL: Record<KnownVerdict, string> = {
  CONFIRMED_VULNERABILITY: "Confirmed vuln",
  CONFIRMED_POTENTIAL: "Confirmed potential",
  DISPUTED_FP: "Disputed FP",
  DOWNGRADED: "Downgraded",
  NEEDS_MANUAL_REVIEW: "Needs review",
  PASS_THROUGH: "Pass-through",
};

export function FilterBar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentSeverity = searchParams.get("severity") as Severity | null;
  const currentVerdict = searchParams.get("verdict");
  const currentPhase = searchParams.get("phase") as Phase | null;

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (value === null || value === "") {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next, { replace: true });
  };

  return (
    <section className={styles.bar} aria-label="Findings filters">
      <div className={styles.group}>
        <span className={styles.groupLabel}>Severity</span>
        <button
          type="button"
          className={`${styles.chip} ${currentSeverity === null ? styles.chipActive : ""}`}
          onClick={() => setParam("severity", null)}
        >
          All
        </button>
        {SEVERITY_LEVELS.map((sev) => (
          <button
            key={sev}
            type="button"
            className={`${styles.chip} ${currentSeverity === sev ? styles.chipActive : ""}`}
            onClick={() => setParam("severity", sev)}
          >
            {sev}
          </button>
        ))}
      </div>

      <div className={styles.group}>
        <span className={styles.groupLabel}>Verdict</span>
        <button
          type="button"
          className={`${styles.chip} ${currentVerdict === null ? styles.chipActive : ""}`}
          onClick={() => setParam("verdict", null)}
        >
          All
        </button>
        {KNOWN_VERDICTS.map((v) => (
          <button
            key={v}
            type="button"
            className={`${styles.chip} ${currentVerdict === v ? styles.chipActive : ""}`}
            onClick={() => setParam("verdict", v)}
            title={v}
          >
            {VERDICT_LABEL[v]}
          </button>
        ))}
      </div>

      <div className={styles.group}>
        <span className={styles.groupLabel}>Phase</span>
        <button
          type="button"
          className={`${styles.chip} ${currentPhase === null ? styles.chipActive : ""}`}
          onClick={() => setParam("phase", null)}
        >
          All
        </button>
        {PHASES.map((p) => (
          <button
            key={p}
            type="button"
            className={`${styles.chip} ${currentPhase === p ? styles.chipActive : ""}`}
            onClick={() => setParam("phase", p)}
          >
            Phase {p}
          </button>
        ))}
      </div>
    </section>
  );
}
