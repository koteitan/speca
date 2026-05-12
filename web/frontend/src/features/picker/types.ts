// TypeScript mirror of `web/server/schemas/picker.py`.
//
// Keep in sync 1:1 with the Pydantic model. Backend is the source of
// truth — drift surfaces as a TS compile error on the consumer side.

export type SavedTargetSource = "history" | "demo";

export interface SavedTarget {
  bug_bounty_url: string | null;
  target_repo: string;
  target_ref: string | null;
  last_run_at: string | null;
  source: SavedTargetSource;
}

// ---------------------------------------------------------------------------
// Slice R2 (NewRunForm) — request / response types for POST /api/runs.
//
// Mirrors `web/server/schemas/run_state.py::RunStartSpec` and the response
// `web/server/schemas/runs.py::RunStartResponse`. Kept hand-written; drift
// surfaces as a TS error at the call site in `useLaunchRun.ts`.
// ---------------------------------------------------------------------------

export interface LaunchSpec {
  bug_bounty_url: string;
  target_repo: string;
  target_ref?: string;
  contract_addresses?: string;
  spec_urls?: string;
  keywords?: string;
  workers: number;
  max_concurrent: number;
  push_to_remote: boolean;
}

export interface LaunchResponse {
  run_id: string;
  branch_name: string;
  workspace_path: string;
  started_at: string;
}
