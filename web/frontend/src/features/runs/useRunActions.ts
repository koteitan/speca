// Slice D2 — mutation hooks for the two write actions on a run.
//
// `useCancelRun(runId)` wraps ``POST /api/runs/{run_id}/cancel`` and
// `useRerunPhases(runId)` wraps ``POST /api/runs/{run_id}/rerun``. Both
// invalidate the run detail + list queries on success so the page
// re-fetches the canonical snapshot; the WebSocket stream (Slice D1)
// will deliver the live state transitions in parallel, but the cache
// refresh is the source of truth that survives a reload.
//
// Error handling: we let `ApiError` (raw envelope from `lib/api.ts`) flow
// up to the page; the page renders it in an error bar matching the
// existing Slice S1 / B4 pattern. This keeps the hook free of i18n
// coupling and matches the v0 "raw envelope on error" convention.
//
// We intentionally do NOT do an optimistic update of `status` here — the
// supervisor races the SIGTERM against the orchestrator's natural
// completion, so the authoritative status comes back via either the WS
// frame or the `invalidateQueries` refetch a few ms later.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type ApiError } from "@/lib/api";

import type { CancelResponse, RerunResponse } from "./types";

/**
 * Mutation for ``POST /api/runs/{run_id}/cancel``.
 *
 * No request body. On success invalidates both the detail query for
 * this run and the runs list (so the run card's badge flips out of
 * `running`).
 */
export function useCancelRun(runId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation<CancelResponse, ApiError, void>({
    mutationFn: () =>
      apiFetch<CancelResponse>(`/runs/${runId}/cancel`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", "detail", runId] });
      queryClient.invalidateQueries({ queryKey: ["runs", "list"] });
    },
  });
}

/**
 * Mutation for ``POST /api/runs/{run_id}/budget_cap``.
 *
 * Body is ``{max_budget_usd: number | null}``. ``null`` clears the cap.
 * Invalidates the detail query so the budget gauge picks up the new
 * cap immediately.
 */
export function useSetBudgetCap(runId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation<
    { run_id: string; max_budget_usd: number | null },
    ApiError,
    { maxBudgetUsd: number | null }
  >({
    mutationFn: (body) =>
      apiFetch<{ run_id: string; max_budget_usd: number | null }>(
        `/runs/${runId}/budget_cap`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ max_budget_usd: body.maxBudgetUsd }),
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", "detail", runId] });
    },
  });
}

/**
 * Mutation for ``POST /api/runs/{run_id}/rerun``.
 *
 * Body is ``{phases: string[], force?: boolean}``. `force` defaults to
 * ``true`` because the UI dialog explicitly tells the user "Selected
 * phases will be re-executed with --force"; we let the caller override
 * if a future surface (e.g. chat) needs a non-force rerun.
 */
export function useRerunPhases(runId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation<
    RerunResponse,
    ApiError,
    { phases: string[]; force?: boolean }
  >({
    mutationFn: (body) =>
      apiFetch<RerunResponse>(`/runs/${runId}/rerun`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phases: body.phases, force: body.force ?? true }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", "detail", runId] });
      queryClient.invalidateQueries({ queryKey: ["runs", "list"] });
    },
  });
}
