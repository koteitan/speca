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
  /** CLI spec §5.3.3 — null means no cap configured. */
  max_budget_usd: number | null;
}

// ---------------------------------------------------------------------------
// Slice D1 — live stream event shapes broadcast over
// `ws://.../api/ws/runs/{run_id}/stream`.
//
// These mirror what `web/server/services/run_supervisor.py` emits (see
// the slice H1 doc); we intentionally keep the fields that the backend
// actually puts on the wire rather than the placeholder shape used in
// the slice spec. `phase_completed` is the backend's event name (not
// `phase_complete`). Extra keys (`run_id`, `parsed`, `raw`) are tolerated
// by the `Record<string, unknown>`-ish open ends below.
// ---------------------------------------------------------------------------

/** Discriminator union for every frame `useRunStream` may receive. */
export type StreamEvent =
  | {
      type: "state_snapshot";
      /**
       * `null` when the backend cannot find the run on disk *and* the
       * supervisor has no live record. The WS router still sends one
       * snapshot frame so the SPA has a stable bookend.
       */
      data: RunDetail | Record<string, unknown> | null;
      reason?: string;
    }
  | {
      type: "phase_started";
      run_id?: string;
      phase: string;
    }
  | {
      type: "phase_progress";
      run_id?: string;
      phase: string;
      /** Free-form payload from the orchestrator's stream-json. */
      snapshot?: Record<string, unknown>;
      /** Optional explicit counters when the backend can extract them. */
      completed?: number;
      total?: number;
    }
  | {
      type: "log_line";
      run_id?: string;
      phase: string;
      line: string;
      /** Parsed JSON payload when the line was a stream-json record. */
      parsed?: Record<string, unknown>;
    }
  | {
      type: "cost_update";
      run_id?: string;
      phase: string;
      delta_usd: number;
      /** Raw parsed JSON the delta was derived from. */
      raw?: Record<string, unknown>;
    }
  | {
      type: "phase_completed";
      run_id?: string;
      phase: string;
      status: PhaseStatus;
      reason?: string | null;
    }
  | {
      type: "run_terminated";
      run_id?: string;
      reason?: string;
      status?: string;
    }
  | {
      type: "log_dropped";
      run_id?: string;
      phase?: string;
      count: number;
    }
  | {
      type: "ping";
      ts: string;
    }
  | {
      type: "error";
      reason: string;
    };

/** Convenience alias for the discriminator literal. */
export type StreamEventType = StreamEvent["type"];

// ---------------------------------------------------------------------------
// Slice D2 — Cancel / Re-run response envelopes.
//
// These mirror the Pydantic models in `web/server/schemas/runs.py` 1:1.
// They live here (rather than in `useRunActions.ts`) so any future slice
// that wants to consume the same envelope (e.g. chat tools surfacing a
// cancel ack) doesn't have to take a dependency on the mutation hook.
// ---------------------------------------------------------------------------

/** Body returned by `POST /api/runs/{run_id}/cancel`. */
export interface CancelResponse {
  run_id: string;
  /**
   * `cancel_requested` when the supervisor still owned the run and a
   * SIGTERM was dispatched; `already_finished` when the run was already
   * terminal on disk (idempotent — UI can treat both as success).
   */
  status: "cancel_requested" | "already_finished";
}

/** Body returned by `POST /api/runs/{run_id}/rerun`. */
export interface RerunResponse {
  run_id: string;
  /** Phases the supervisor has scheduled for re-execution. */
  rerun_phases: string[];
}
