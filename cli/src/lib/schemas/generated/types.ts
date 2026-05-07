/**
 * AUTO-GENERATED type aliases derived from the JSON Schemas in this directory.
 * Edit the Pydantic models in `scripts/orchestrator/schemas.py` and
 * regenerate via `npm run sync-schemas`.
 */
/**
 * AUTO-GENERATED — DO NOT EDIT.
 * Source: schemas/<Name>.schema.json (Pydantic-derived).
 * Run `npm run sync-schemas` to refresh.
 */

export type TargetCommit = string;
export type TargetCommitShort = string;
export type TargetRefLabel = string;
export type TargetRefType = string;
export type TargetRepo = string;

/**
 * Target repository information (outputs/TARGET_INFO.json).
 *
 * Created by the 02c CI workflow before Phase 02c runs. Consumed by
 * Phases 02c, 03, and 04 for target repository/commit consistency.
 */
export interface TargetInfo {
  target_commit?: TargetCommit;
  target_commit_short?: TargetCommitShort;
  target_ref_label?: TargetRefLabel;
  target_ref_type?: TargetRefType;
  target_repo: TargetRepo;
}

/**
 * AUTO-GENERATED — DO NOT EDIT.
 * Source: schemas/<Name>.schema.json (Pydantic-derived).
 * Run `npm run sync-schemas` to refresh.
 */

export type InScopeComponents = string[];
export type InheritedFrom = string;
export type OutOfScopeComponents = string[];
export type ProgramName = string;
export type ProgramUrl = string;
export type ScopeNotes = string[];

/**
 * Bug bounty scope information.
 */
export interface BugBountyScopeInfo {
  in_scope_components?: InScopeComponents;
  inherited_from?: InheritedFrom;
  out_of_scope_components?: OutOfScopeComponents;
  program_name?: ProgramName;
  program_url?: ProgramUrl;
  scope_notes?: ScopeNotes;
  severity_classification?: SeverityClassification;
}
export interface SeverityClassification {
  [k: string]: unknown;
}
