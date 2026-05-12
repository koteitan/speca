// React Query hook for `/api/picker/saved`.
//
// Slice F owns this endpoint; Slice B (Run List) and the v1 Project
// Picker form both consume the hook to pre-fill the audit form. Keeping
// the query key as a tuple makes invalidation from later mutations
// (POST /picker/saved in v1) trivial.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { apiFetch } from "../../lib/api";
import type { SavedTarget } from "./types";

export const savedTargetsQueryKey = ["picker", "saved"] as const;

export function useSavedTargets(): UseQueryResult<SavedTarget[]> {
  return useQuery<SavedTarget[]>({
    queryKey: savedTargetsQueryKey,
    queryFn: () => apiFetch<SavedTarget[]>("/picker/saved"),
  });
}
