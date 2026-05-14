// Slice D3 — Budget gauge for the RunDetailPage header.
//
// Implements CLI spec §5.3.3 ("Budget gauge"): a thin horizontal bar
// that shows `spent / cap` from the runner's CostTracker, turning yellow
// at 80% and red at 100%. The CLI version halts at 100% and prompts to
// bump the cap; the web version is read-only for now, so we surface the
// same information via colour + a tooltip instead of a modal.
//
// Why a separate component instead of inlining into RunDetailPage:
//
//   * Phase 04 / chat / picker may want to embed the same gauge later
//     (e.g. inside an approval card preview). Lifting it out keeps the
//     `oklch(...)` thresholds and aria semantics in one place.
//   * The cap is intentionally a prop, not a hook. The backend
//     `RunDetail` shape does not yet carry `max_budget_usd` (the spec is
//     on the `spec.max_budget_usd` side, not the run snapshot). The
//     caller can pass `null` to render the "no cap configured" form,
//     and a future PR can thread the real cap through without changing
//     this component's contract.
//
// Accessibility notes:
//
//   * The outer container is `role="progressbar"` with explicit aria
//     min/max/now so screen readers announce the usage percentage.
//   * When `cap === null` we omit `aria-valuemax` / `aria-valuenow`
//     because "no cap" has no meaningful progressbar semantics; we keep
//     the visible text-only fallback so the row still communicates the
//     spent amount.
//   * The colour thresholds rely on tooltip text, not colour alone, to
//     stay WCAG 1.4.1 friendly.

import { useT } from "@/i18n/useT";

import styles from "./BudgetGauge.module.css";

/** Inputs from the caller. See module-level comment for the contract. */
export interface BudgetGaugeProps {
  /** USD spent so far (cumulative across phases). */
  spent: number;
  /** USD cap, or `null` when no cap is configured / known. */
  cap: number | null;
  /** Visual density. `compact` is for inline use in a meta row. */
  size?: "compact" | "regular";
}

/** Format a USD amount as `$1.23`. Negative or NaN values clamp to 0. */
function formatUsd(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "$0.00";
  return `$${value.toFixed(2)}`;
}

/**
 * Compute usage percentage as an integer for display, plus the raw
 * 0..1 ratio for the bar width. We intentionally clamp the bar fill
 * at 100% so the visual stays bounded, while the *label* can still
 * read "120%" — that's how the user notices they blew the cap.
 *
 * Returns `null` when the cap is not usable (null / 0 / negative /
 * non-finite). The caller treats this as the "no cap" rendering path,
 * which avoids any division-by-zero footgun.
 */
function computeUsage(
  spent: number,
  cap: number | null,
): { ratio: number; pct: number } | null {
  if (cap === null) return null;
  if (!Number.isFinite(cap) || cap <= 0) return null;
  const safeSpent = Number.isFinite(spent) && spent > 0 ? spent : 0;
  const ratio = safeSpent / cap;
  const pct = Math.round(ratio * 100);
  return { ratio, pct };
}

/**
 * Thin progress-bar style budget gauge.
 *
 * Renders three visual states keyed off the spent/cap ratio:
 *
 *   * `<80%`  — neutral (Nyx primary)
 *   * `80..99%` — yellow accent, warning tooltip
 *   * `>=100%`  — red, "budget cap exceeded" tooltip
 *
 * When no cap is provided we degrade gracefully to a text-only
 * "Spent $X.XX — no cap configured" line so the surrounding meta row
 * still aligns with the other items.
 */
export function BudgetGauge({
  spent,
  cap,
  size = "compact",
}: BudgetGaugeProps) {
  const t = useT();
  const usage = computeUsage(spent, cap);

  // "No cap" branch — text-only fallback. We still wrap in the same
  // container element so consumers can style the gauge slot uniformly.
  if (usage === null) {
    const noCapLabel = t("runs.detail.budget_gauge.spent_no_cap", {
      spent: formatUsd(spent),
    });
    return (
      <span
        className={`${styles.gauge} ${
          size === "regular" ? styles.regular : styles.compact
        } ${styles.noCap}`}
        data-testid="budget-gauge"
        data-state="no-cap"
      >
        <span className={styles.label}>{noCapLabel}</span>
      </span>
    );
  }

  const { ratio, pct } = usage;
  const state = pct >= 100 ? "over" : pct >= 80 ? "warning" : "normal";
  const fillClass =
    state === "over"
      ? styles.over
      : state === "warning"
        ? styles.warning
        : styles.normal;

  // Tooltip / title is only attached for the warning/over states — the
  // neutral state stays quiet so we don't pile a tooltip onto every run.
  const tooltip =
    state === "over"
      ? t("runs.detail.budget_gauge.tooltip_over")
      : state === "warning"
        ? t("runs.detail.budget_gauge.tooltip_warn")
        : undefined;

  const label = t("runs.detail.budget_gauge.spent_of_cap", {
    spent: formatUsd(spent),
    // We already know `cap` is finite & positive because `computeUsage`
    // would have returned null otherwise. The non-null assertion keeps
    // TS honest about the narrowed type.
    cap: formatUsd(cap as number),
    pct,
  });

  // Clamp the visible bar fill at 100%. The numeric label keeps the
  // true value (e.g. "120%") so over-budget runs are not visually
  // indistinguishable from exactly-at-cap ones.
  const fillWidth = Math.min(1, ratio) * 100;

  return (
    <span
      className={`${styles.gauge} ${
        size === "regular" ? styles.regular : styles.compact
      }`}
      data-testid="budget-gauge"
      data-state={state}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={cap as number}
      aria-valuenow={Math.max(0, Number.isFinite(spent) ? spent : 0)}
      aria-label={label}
      title={tooltip}
    >
      <span className={styles.barTrack}>
        <span
          className={`${styles.barFill} ${fillClass}`}
          style={{ width: `${fillWidth}%` }}
        />
      </span>
      <span className={styles.label}>{label}</span>
    </span>
  );
}

export default BudgetGauge;
