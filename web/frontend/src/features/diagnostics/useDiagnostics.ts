// Hook: `useDiagnostics`
//
// Wraps `/api/diagnostics` in a TanStack Query. 30s `staleTime` matches
// the implicit cache life of the backend's `cli_detect` snapshot — pulling
// it lower would force unnecessary subprocess work on the user's machine
// without a UX gain (the page is opened deliberately, not on every nav).
//
// The companion `useInvalidateDiagnostics` lets a future "Refresh" button
// drop the cache without us having to thread a `refetch()` ref through
// the section components.

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

import type { DiagnosticsReport } from "./types";

export const diagnosticsQueryKey = ["diagnostics"] as const;

export function useDiagnostics() {
  return useQuery({
    queryKey: diagnosticsQueryKey,
    queryFn: () => apiFetch<DiagnosticsReport>("/diagnostics"),
    staleTime: 30 * 1000,
  });
}

export function useInvalidateDiagnostics() {
  const queryClient = useQueryClient();
  return () =>
    queryClient.invalidateQueries({ queryKey: diagnosticsQueryKey });
}
