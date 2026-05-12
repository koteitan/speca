// Hook: `useIntegrationsStatus`
//
// Wraps `/api/integrations/status` in a TanStack Query so any component
// can ask "is `code` installed?" without re-implementing the cache key.
//
// The 60s `staleTime` matches the server-side TTL (30s in cli_detect) with
// enough buffer that a single refetch round-trip after focus / mount is
// the worst case — pulling this number lower would cause unnecessary
// subprocess work on the backend without a UX win.

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface CliDetected {
  installed: boolean;
  version: string | null;
}

export interface GhStatus extends CliDetected {
  authed: boolean | null;
}

export interface IntegrationsStatus {
  code: CliDetected;
  gh: GhStatus;
}

export const integrationsStatusQueryKey = ["integrations", "status"] as const;

export function useIntegrationsStatus() {
  return useQuery({
    queryKey: integrationsStatusQueryKey,
    queryFn: () => apiFetch<IntegrationsStatus>("/integrations/status"),
    staleTime: 60 * 1000,
  });
}

// Absolute filesystem paths returned by ``GET /api/integrations/paths``.
// Slice G uses these to feed ``<OpenInVSCode>`` placements — the frontend
// has no other way to learn the SPECA repo root.
export interface IntegrationPaths {
  repo_root: string;
  speca_dir: string;
  claude_dir: string;
}

export const integrationsPathsQueryKey = ["integrations", "paths"] as const;

export function useIntegrationsPaths() {
  return useQuery({
    queryKey: integrationsPathsQueryKey,
    queryFn: () => apiFetch<IntegrationPaths>("/integrations/paths"),
    // Paths are derived from server-side config constants that do not
    // change during a session — cache aggressively.
    staleTime: 5 * 60 * 1000,
  });
}
