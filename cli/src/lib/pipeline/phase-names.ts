/**
 * Friendly names for the SPECA pipeline phases. Mirrors
 * `scripts/orchestrator/config.py::PHASE_CONFIGS` (read-only — the Python
 * side stays the source of truth; we only need labels for the dashboard
 * and this list rarely changes).
 *
 * `KNOWN_PHASE_IDS` is the closed set of phase ids the CLI knows about; the
 * derived `KnownPhaseId` union is useful in tests and at internal call sites
 * where we want a typo to fail compilation. At the orchestrator boundary
 * (`phaseName`) we still accept arbitrary strings and fall back to the id
 * itself so a fork that adds new phases renders cleanly.
 */
export const KNOWN_PHASE_IDS = ["01a", "01b", "01e", "02c", "03", "04"] as const;
export type KnownPhaseId = (typeof KNOWN_PHASE_IDS)[number];

export function isKnownPhaseId(value: string): value is KnownPhaseId {
  return (KNOWN_PHASE_IDS as readonly string[]).includes(value);
}

export const PHASE_NAMES: Record<KnownPhaseId, string> = {
  "01a": "Spec Discovery",
  "01b": "Subgraph Extraction",
  "01e": "Property Generation",
  "02c": "Code Pre-resolution",
  "03": "Audit Map",
  "04": "Audit Review",
};

export function phaseName(id: string): string {
  return isKnownPhaseId(id) ? PHASE_NAMES[id] : id;
}
