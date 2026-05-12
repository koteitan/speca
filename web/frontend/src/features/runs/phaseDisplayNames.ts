// Phase ID -> human label.
//
// SOURCE OF TRUTH for SPECA phase labels in the UI. Other slices (e.g.
// findings filter dropdown, chat tool descriptions) MUST import from
// here so the language stays consistent — Slice B owns this map for v0.
//
// Order matches `KNOWN_PHASE_ORDER` in
// `web/server/services/run_status.py`. Update both together when a new
// phase is added.
export const PHASE_DISPLAY_NAMES: Record<string, string> = {
  "01a": "Spec Discovery",
  "01b": "Subgraph Extraction",
  "01e": "Property Generation",
  "02c": "Code Pre-resolution",
  "03": "Audit Map",
  "04": "Review",
};

/**
 * Format `01a` as `01a Spec Discovery`. Unknown ids fall back to the id
 * alone so future phases (e.g. `05`) don't render as `undefined`.
 */
export function formatPhaseLabel(phaseId: string): string {
  const name = PHASE_DISPLAY_NAMES[phaseId];
  return name ? `${phaseId} ${name}` : phaseId;
}
