// Diagnostics types — mirror of `web/server/schemas/diagnostics.py`.
//
// The two surfaces are tied together at the JSON layer; keeping the names
// identical (`installed`, `version`, `status`, `details`) means a future
// generated-types pass over the FastAPI OpenAPI schema can drop in here
// with zero rename churn.

export type ToolStatusValue = "ok" | "missing" | "outdated" | "unknown";

export interface ToolStatus {
  name: string;
  installed: boolean;
  version: string | null;
  status: ToolStatusValue;
  /**
   * Tool-specific extras. Examples we render today:
   *
   * - `{ authed: boolean | null }` for `gh` so the SPA can show
   *   "logged in" / "not logged in" without a second round trip.
   * - `{ min_version: "20.0.0", parsed_version: "22.4.1" }` for
   *   `node` so the user sees the threshold next to the chip.
   */
  details?: Record<string, unknown> | null;
}

export interface AuthStatus {
  logged_in: boolean;
  method: "oauth" | "api_key" | null;
  identity: string | null;
}

export interface DiagnosticsReport {
  node: ToolStatus;
  uv: ToolStatus;
  git: ToolStatus;
  claude: ToolStatus;
  gh: ToolStatus;
  code: ToolStatus;
  auth: AuthStatus;
  api_key_configured: boolean;
}
