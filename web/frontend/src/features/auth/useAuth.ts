// React Query hooks for the auth router.
//
// Server state (`logged_in`, `method`, `identity`) lives in TanStack Query
// under the `['auth', 'status']` key — any mutation in this module
// invalidates that key so the SPA re-fetches the truth from the backend
// instead of guessing client-side. The raw API key flows in via mutation
// body only and is dropped from React state immediately after the call.

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { apiFetch } from "../../lib/api";
import type {
  ApiKeyRequest,
  AuthStatus,
  OAuthLoginStubResponse,
} from "./types";

export const authStatusQueryKey = ["auth", "status"] as const;

export function useAuthStatus(options?: { polling?: boolean }): UseQueryResult<AuthStatus> {
  return useQuery<AuthStatus>({
    queryKey: authStatusQueryKey,
    queryFn: () => apiFetch<AuthStatus>("/auth/status"),
    // While the OAuth flow is in progress the SPA stays on /login waiting
    // for credentials.json to update. Poll every 2s so the user sees the
    // logged-in state moments after they finish the browser handshake.
    refetchInterval: options?.polling ? 2000 : false,
  });
}

export function useLoginWithApiKey(): UseMutationResult<
  AuthStatus,
  Error,
  ApiKeyRequest
> {
  const queryClient = useQueryClient();
  return useMutation<AuthStatus, Error, ApiKeyRequest>({
    mutationFn: (body) =>
      apiFetch<AuthStatus>("/auth/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (status) => {
      // Prime the cache with the post-write status returned by the backend
      // so the UI flips to "logged in" without an extra round trip, then
      // invalidate to let any other consumer re-read on next focus.
      queryClient.setQueryData(authStatusQueryKey, status);
      queryClient.invalidateQueries({ queryKey: authStatusQueryKey });
    },
  });
}

// Stub for the OAuth (claude.ai) entrypoint. In v0 the UI button is
// disabled, but exporting the hook keeps the surface area stable for v1.
export function useStartOAuth(): UseMutationResult<
  OAuthLoginStubResponse,
  Error,
  void
> {
  return useMutation<OAuthLoginStubResponse, Error, void>({
    mutationFn: () =>
      apiFetch<OAuthLoginStubResponse>("/auth/login", { method: "POST" }),
  });
}
