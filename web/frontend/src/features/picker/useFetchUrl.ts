// React Query mutation for `/api/picker/fetch_url`.
//
// Slice B3 (backend) returns a flat scope payload — the SPA only needs
// one round trip to populate the Project Picker "From URL" form.
// Errors are surfaced via the standard FastAPI `{detail}` envelope; we
// re-throw a typed shape so the consumer can branch on the discriminator
// without re-parsing the response body.
//
// We intentionally don't auto-retry: the underlying Anthropic call can
// be slow and expensive, the user is staring at a spinner, and the
// backend already maps transient failures to `retryable=true` so the UI
// can offer a manual "Retry" affordance.

import { useMutation, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api";

export interface FetchUrlRequest {
  bug_bounty_url: string;
  contract_addresses?: string | null;
}

export interface ScopeContract {
  address: string;
  network?: string | null;
  name?: string | null;
}

// Mirrors `web/server/schemas/picker.py::FetchUrlResponse`. Kept hand-
// written (rather than generated) because the surface is tiny and the
// drift will surface as a TS error at every call site.
export interface FetchUrlResponse {
  program_url: string;
  program_name?: string | null;
  in_scope_assets: string[];
  in_scope_contracts: ScopeContract[];
  out_of_scope: string[];
  severity_ratings?: string | null;
  reward_range?: string | null;
  notes?: string | null;
  spec_urls: string;
  keywords: string;
}

// Discriminator literals match what `web/server/routers/picker.py` raises
// in its `HTTPException` details — we keep both in sync by hand because
// the surface is small and high-signal.
export type FetchUrlErrorCode =
  | "anthropic_unreachable"
  | "invalid_scope_response"
  | "unknown";

export interface FetchUrlError {
  code: FetchUrlErrorCode;
  retryable: boolean;
  message: string;
  status: number;
}

function parseDetail(body: string): {
  error?: string;
  retryable?: boolean;
  message?: string;
} | null {
  try {
    const parsed = JSON.parse(body) as {
      detail?:
        | string
        | { error?: string; retryable?: boolean; message?: string };
    };
    if (!parsed.detail) return null;
    if (typeof parsed.detail === "string") {
      return { message: parsed.detail };
    }
    return parsed.detail;
  } catch {
    return null;
  }
}

function toFetchUrlError(err: unknown): FetchUrlError {
  if (err instanceof ApiError) {
    const detail = parseDetail(err.body);
    const rawCode = detail?.error;
    const code: FetchUrlErrorCode =
      rawCode === "anthropic_unreachable" ||
      rawCode === "invalid_scope_response"
        ? rawCode
        : "unknown";
    return {
      code,
      retryable: Boolean(detail?.retryable),
      message: detail?.message ?? err.message,
      status: err.status,
    };
  }
  return {
    code: "unknown",
    retryable: false,
    message: err instanceof Error ? err.message : String(err),
    status: 0,
  };
}

export function useFetchUrl(): UseMutationResult<
  FetchUrlResponse,
  FetchUrlError,
  FetchUrlRequest
> {
  return useMutation<FetchUrlResponse, FetchUrlError, FetchUrlRequest>({
    mutationFn: async (req) => {
      try {
        return await apiFetch<FetchUrlResponse>("/picker/fetch_url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            bug_bounty_url: req.bug_bounty_url,
            contract_addresses: req.contract_addresses ?? null,
          }),
        });
      } catch (err) {
        throw toFetchUrlError(err);
      }
    },
    retry: false,
  });
}
