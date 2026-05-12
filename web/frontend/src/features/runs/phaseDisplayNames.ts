// Phase ID -> human label.
//
// SOURCE OF TRUTH for SPECA phase labels in the UI. Other slices (e.g.
// findings filter dropdown, chat tool descriptions) MUST import from
// here so the language stays consistent — Slice B owns this map for v0.
//
// Order matches `KNOWN_PHASE_ORDER` in
// `web/server/services/run_status.py`. Update both together when a new
// phase is added.
//
// Slice I2 — display names now come from i18n. `PHASE_IDS` keeps the
// canonical order; the translated label is resolved at render time via
// `i18next.t("runs.phase_names.<id>")`. Callers that already had a
// `t` from `useT()` can pass it in; non-React callers fall back to the
// global `i18next` instance.

import i18next from "@/i18n";

export const PHASE_IDS: readonly string[] = [
  "01a",
  "01b",
  "01e",
  "02c",
  "03",
  "04",
] as const;

/**
 * Resolve the display name for a phase id via the current language. The
 * caller is responsible for being inside a React render with a synced
 * i18next state; we fall back to the id if the key is missing so unknown
 * phases (e.g. a future `05`) don't render as `undefined`.
 */
export function resolvePhaseName(phaseId: string): string {
  const key = `runs.phase_names.${phaseId}`;
  const name = i18next.t(key);
  // i18next returns the key itself when the resource is missing — treat
  // that as "no translation available" and fall through to the bare id.
  if (typeof name !== "string" || name === key) {
    return phaseId;
  }
  return name;
}

/**
 * Format `01a` as `01a Spec Discovery`. Unknown ids fall back to the id
 * alone so future phases (e.g. `05`) don't render as `undefined`.
 */
export function formatPhaseLabel(phaseId: string): string {
  const name = i18next.t(`runs.phase_names.${phaseId}`);
  if (typeof name !== "string" || name === `runs.phase_names.${phaseId}`) {
    return phaseId;
  }
  return `${phaseId} ${name}`;
}
