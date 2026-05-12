// Mutation hook: `useOpenInVSCode`
//
// Wraps `POST /api/integrations/open-in-vscode` so that every consumer
// (the `<OpenInVSCode>` button, future context menus, etc.) shares the
// same fire-and-forget semantics and the same v0 "alert toast".
//
// v0 uses `window.alert` for the success/failure surface. A proper toast
// component is on the roadmap, but the contract here is intentionally
// narrow (a single `notify` callback we can swap out) so the upgrade is
// a one-file change.

import { useMutation } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api";

export interface OpenInVSCodePayload {
  path: string;
  line?: number;
}

export interface OpenInVSCodeResponse {
  ok: boolean;
}

// Pulled out so tests / Storybook can swap in a non-blocking notifier.
function defaultNotify(message: string): void {
  // eslint-disable-next-line no-alert
  window.alert(message);
}

function extractHint(error: unknown): string {
  if (error instanceof ApiError) {
    try {
      const parsed = JSON.parse(error.body) as {
        detail?: { hint?: string; error?: string } | string;
      };
      const detail = parsed.detail;
      if (detail && typeof detail === "object" && detail.hint) {
        return detail.hint;
      }
      if (typeof detail === "string") {
        return detail;
      }
    } catch {
      // body wasn't JSON; fall through to the raw status
    }
    return `HTTP ${error.status}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export function useOpenInVSCode(notify: (message: string) => void = defaultNotify) {
  return useMutation<OpenInVSCodeResponse, unknown, OpenInVSCodePayload>({
    mutationFn: (payload) =>
      apiFetch<OpenInVSCodeResponse>("/integrations/open-in-vscode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      notify("VSCode で開きました");
    },
    onError: (error) => {
      notify(`起動に失敗: ${extractHint(error)}`);
    },
  });
}
