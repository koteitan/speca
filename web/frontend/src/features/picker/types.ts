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
