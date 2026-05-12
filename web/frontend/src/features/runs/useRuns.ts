import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

import type { RunDetail, RunSummary } from "./types";

/**
 * Fetch the list of recent runs.
 *
 * The query key is namespaced so future invalidations (e.g. after the
 * v1 "+ New run" button kicks off a phase) can target either the list
 * or a specific detail page.
 */
export function useRunList() {
  return useQuery({
    queryKey: ["runs", "list"],
    queryFn: () => apiFetch<RunSummary[]>("/runs"),
  });
}

/**
 * Fetch the detail payload for one run.
 *
 * @param runId — pass `undefined` when the route param isn't known yet
 *                (the query stays disabled until a value is present)
 */
export function useRunDetail(runId: string | undefined) {
  return useQuery({
    queryKey: ["runs", "detail", runId],
    queryFn: () => apiFetch<RunDetail>(`/runs/${runId}`),
    enabled: Boolean(runId),
  });
}
