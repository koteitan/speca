// TypeScript mirror of `web/server/schemas/auth.py`.
//
// Keep these in sync 1:1 with the Pydantic models — the backend is the
// source of truth. The SPA never sees raw key material; `AuthStatus`
// intentionally lacks any field that would carry it.

export type AuthMethod = "oauth" | "api_key";

export interface AuthStatus {
  logged_in: boolean;
  method: AuthMethod | null;
  identity: string | null;
}

export interface ApiKeyRequest {
  key: string;
}

export interface OAuthLoginStubResponse {
  status: "not_implemented_in_v0";
  hint: string;
}
