// Defensive wrapper around Slice A's `useAuthStatus`.
//
// Why a wrapper? AppShell needs to know "are we logged in?" but must not
// crash if Slice A's hook file ever moves or its return shape changes
// during parallel development. Wrapping behind a single hook means
// AppShell / Header consume a fixed contract:
//
//   { loggedIn, identity, isPending, isError }
//
// regardless of how Slice A evolves underneath.

import { useAuthStatus } from "./useAuth";

export interface SafeAuthStatus {
  loggedIn: boolean;
  identity: string | null;
  /** Initial fetch in flight — treat as "don't redirect yet". */
  isPending: boolean;
  isError: boolean;
}

export function useAuthStatusSafe(): SafeAuthStatus {
  // `useAuthStatus` is a TanStack Query hook — wrap defensively so any
  // future TS-level shape change here surfaces as a compile error in this
  // single adapter file instead of every call site.
  const query = useAuthStatus();
  const data = query.data;
  return {
    loggedIn: Boolean(data?.logged_in),
    identity: data?.identity ?? null,
    isPending: query.isPending,
    isError: query.isError,
  };
}
