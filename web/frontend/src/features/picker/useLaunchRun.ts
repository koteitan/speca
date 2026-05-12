// React Query mutation for `POST /api/runs` (Slice B1 backend).
//
// Slice R2 (NewRunForm) calls this with the assembled draft. The backend
// returns 202 + `{ run_id, branch_name, workspace_path, started_at }`,
// after which the form navigates to `/runs/<run_id>`.
//
// Error envelopes (mirrors `web/server/routers/runs.py`):
//   - 422 `invalid_target_repo`     — bad `owner/repo` shape
//   - 422 `invalid_workspace_input` — unsupported URL chars, etc.
//   - 422 `ref_not_found`           — `target_ref` not in remote
//   - 502 `clone_failed`            — `git clone --bare` failed
//   - 502 `worktree_failed`         — `git worktree add` failed
//   - 503 `anthropic_unreachable`   — surfaced indirectly (not raised here
//                                     today, but the form maps it for
//                                     symmetry with the picker)
//
// The mutation re-throws raw `ApiError` so the form can branch on the
// parsed envelope. We do NOT auto-retry: 422 / 502 are caller-fixable and
// `git clone` retries can be expensive.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api";

import type { LaunchResponse, LaunchSpec } from "./types";

export function useLaunchRun(): UseMutationResult<
  LaunchResponse,
  ApiError,
  LaunchSpec
> {
  const queryClient = useQueryClient();

  return useMutation<LaunchResponse, ApiError, LaunchSpec>({
    mutationFn: (spec) =>
      apiFetch<LaunchResponse>("/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(spec),
      }),
    retry: false,
    onSuccess: () => {
      // Surface the freshly-spawned run on the next visit to /runs.
      void queryClient.invalidateQueries({ queryKey: ["runs", "list"] });
    },
  });
}
