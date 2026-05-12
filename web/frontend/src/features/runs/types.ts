// TypeScript mirrors of the Pydantic schemas in
// `web/server/schemas/runs.py`. Keep these 1:1 — adding a field on the
// backend means adding it here too. The runtime payload is whatever the
// Pydantic models emit via FastAPI's response_model, so optional fields
// always come over the wire (just with `null`).

export type RunStatus = "ok" | "running" | "failed" | "cancelled";

export type PhaseStatus =
  | "ok"
  | "running"
  | "pending"
  | "failed"
  | "cancelled"
  | "skipped";

export interface RunSummary {
  run_id: string;
  /** ISO 8601 timestamp (Pydantic emits UTC with timezone). */
  started_at: string;
  ended_at: string | null;
  target_slug: string | null;
  status: RunStatus;
  cost_usd_total: number;
  phases_completed: string[];
}

export interface PhaseRow {
  phase_id: string;
  status: PhaseStatus;
  duration_seconds: number | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface RunDetail extends RunSummary {
  phases: PhaseRow[];
  target_info: Record<string, unknown> | null;
  spec_sources: string[];
  prompt_shas: Record<string, string>;
  branch_name: string | null;
}
