// Mutation hook: `useFork`
//
// Wraps `POST /api/integrations/fork` (Slice B4). The request always sets
// `confirmed: true` because the UI layer gates the call behind a
// `<ConfirmDialog>` — the server returns 400 with `confirmation_required`
// if the flag is missing, which we surface defensively for the case where
// somebody calls `mutate` outside the dialog path.
//
// Errors from B4 use a structured envelope: `{error, hint?, detail?}`
// nested under FastAPI's `detail` field. We parse that here and expose a
// `useForkErrorMessage()` helper that callers can hand straight to i18n.

import { useMutation } from "@tanstack/react-query";
import { useCallback } from "react";
import type { TFunction } from "i18next";

import { ApiError, apiFetch } from "@/lib/api";
import { useT } from "@/i18n/useT";

// ---- Request / response shapes ---------------------------------------------

export interface ForkPayload {
  target_repo: string;
  into_owner?: string;
  confirmed: true;
}

export interface ForkResponse {
  fork_url: string;
  forked_repo: string;
}

/**
 * Decoded form of the B4 error envelope. The server returns
 * ``{detail: {error, hint?, detail?}}`` for known failure modes; we strip
 * the outer ``detail`` wrapper so call sites can match on ``error`` alone.
 */
export interface ForkError {
  error: string;
  hint?: string;
  detail?: string;
}

// ---- Envelope extraction ----------------------------------------------------

function parseForkError(err: unknown): ForkError {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.body) as {
        detail?: Partial<ForkError> | string;
      };
      const detail = parsed.detail;
      if (detail && typeof detail === "object" && typeof detail.error === "string") {
        return {
          error: detail.error,
          hint: typeof detail.hint === "string" ? detail.hint : undefined,
          detail: typeof detail.detail === "string" ? detail.detail : undefined,
        };
      }
      if (typeof detail === "string") {
        return { error: "unknown", hint: detail };
      }
    } catch {
      // Body wasn't JSON — fall through.
    }
    return { error: "unknown", hint: `HTTP ${err.status}` };
  }
  if (err instanceof Error) {
    return { error: "unknown", hint: err.message };
  }
  return { error: "unknown", hint: String(err) };
}

// ---- i18n-aware message helper ---------------------------------------------

/**
 * Map a parsed ForkError to a user-facing string. Kept separate from the
 * mutation hook so tests and Storybook can render every error variant
 * without spinning up a QueryClient.
 */
export function formatForkError(err: ForkError, t: TFunction): string {
  switch (err.error) {
    case "gh_cli_not_found":
      return t("settings.fork.error.gh_missing");
    case "gh_not_authed":
      return t("settings.fork.error.gh_unauthed");
    case "gh_fork_failed": {
      const base = t("settings.fork.error.fork_failed");
      // detail is the raw stderr from `gh repo fork` — include it so the
      // user can diagnose "repository not found" / rate-limit without
      // checking server logs.
      return err.detail ? `${base}: ${err.detail}` : base;
    }
    case "confirmation_required":
      // Should not be reachable from the UI (we always send confirmed:
      // true) but defensively cover it.
      return t("settings.fork.error.confirmation_required");
    default:
      return err.hint ?? t("common.error");
  }
}

// ---- Hook -------------------------------------------------------------------

/**
 * React Query mutation for ``POST /api/integrations/fork``.
 *
 * Returns the raw TanStack mutation object plus a memoised ``errorMessage``
 * derived from the parsed B4 envelope. Consumers should always read the
 * message via ``mutation.errorMessage`` — formatting the error in render
 * directly couples the component to the envelope shape we want to keep
 * inside this file.
 */
export function useFork() {
  const t = useT();

  const mutation = useMutation<ForkResponse, unknown, ForkPayload>({
    mutationFn: (payload) =>
      apiFetch<ForkResponse>("/integrations/fork", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
  });

  // Pre-format the error message so the page doesn't need to reach for
  // ``parseForkError`` itself. We memo via ``useCallback`` so the returned
  // closure has a stable identity across renders.
  const getErrorMessage = useCallback((): string | null => {
    if (!mutation.isError) return null;
    return formatForkError(parseForkError(mutation.error), t);
  }, [mutation.isError, mutation.error, t]);

  return {
    ...mutation,
    errorMessage: getErrorMessage(),
  };
}

export type { ForkError as ForkErrorEnvelope };
