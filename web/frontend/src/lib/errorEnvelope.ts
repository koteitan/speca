// errorEnvelope — central translation of backend `ApiError` envelopes
// into structured surfaces the UI can render uniformly.
//
// SPECA_CLI_SPEC §10.4 enumerates the failure cases a user can hit
// while starting / driving a run; this module maps the backend error
// codes onto i18n key prefixes so callers stay free of switch-on-string
// boilerplate.
//
// The 7 cases the spec specifically calls out:
//   1. clone_failed           — `git clone` failed (network, auth, …)
//   2. invalid_target_repo    — slug shape wrong (server-side regex)
//   3. ref_not_found          — branch / tag / commit missing on origin
//   4. worktree_failed        — `git worktree add` failed locally
//   5. anthropic_unreachable  — Picker scope fetch hit a network error
//   6. run_not_found          — referenced run id not on disk
//   7. still_running          — rerun/cancel conflicts with live state
//
// Each gets a dedicated i18n key under `errors.<code>.title/message`.
// Unknown codes fall back to a generic "unexpected error" key with the
// raw body shown below so the operator can copy/paste it into a bug.

import { ApiError } from "./api";

export type KnownErrorCode =
  | "clone_failed"
  | "invalid_target_repo"
  | "invalid_workspace_input"
  | "ref_not_found"
  | "worktree_failed"
  | "anthropic_unreachable"
  | "run_not_found"
  | "still_running"
  | "invalid_phases";

export interface ErrorEnvelope {
  /** Canonical lower_snake_case code, or null for an HTTP-only error. */
  code: KnownErrorCode | string | null;
  /** Free-text message from the backend; never falsy if `code` is null. */
  message: string;
  /** HTTP status code, when known. */
  status: number | null;
  /** True when ``code`` is one of the seven §10.4 cases. */
  isKnown: boolean;
  /** Raw envelope body — preserved so a "show raw" disclosure can render
   *  the operator-readable JSON without re-parsing. */
  raw: string;
}

const KNOWN_CODES: ReadonlySet<string> = new Set<KnownErrorCode>([
  "clone_failed",
  "invalid_target_repo",
  "invalid_workspace_input",
  "ref_not_found",
  "worktree_failed",
  "anthropic_unreachable",
  "run_not_found",
  "still_running",
  "invalid_phases",
]);

/**
 * Parse any ``unknown`` error (typically the ``error`` field from a
 * TanStack mutation) into the structured envelope. Non-``ApiError``
 * inputs degrade to ``{ code: null, message: String(err), status: null }``
 * so the caller never has to special-case "this is not an ApiError".
 */
export function parseErrorEnvelope(err: unknown): ErrorEnvelope {
  if (err instanceof ApiError) {
    let detail: unknown = null;
    try {
      const parsed = JSON.parse(err.body) as { detail?: unknown };
      detail = parsed.detail ?? null;
    } catch {
      // Body wasn't JSON; treat the raw body as the message.
    }

    if (detail && typeof detail === "object") {
      const code = (detail as { error?: unknown }).error;
      const message = (detail as { message?: unknown }).message;
      const codeStr = typeof code === "string" ? code : null;
      return {
        code: codeStr,
        message:
          typeof message === "string" && message
            ? message
            : err.body || `HTTP ${err.status}`,
        status: err.status,
        isKnown: codeStr !== null && KNOWN_CODES.has(codeStr),
        raw: err.body,
      };
    }

    if (typeof detail === "string") {
      return {
        code: null,
        message: detail,
        status: err.status,
        isKnown: false,
        raw: err.body,
      };
    }

    return {
      code: null,
      message: err.body || `HTTP ${err.status}`,
      status: err.status,
      isKnown: false,
      raw: err.body,
    };
  }

  if (err instanceof Error) {
    return {
      code: null,
      message: err.message,
      status: null,
      isKnown: false,
      raw: err.message,
    };
  }

  return {
    code: null,
    message: String(err),
    status: null,
    isKnown: false,
    raw: String(err),
  };
}
