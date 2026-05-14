// Tiny fetch helper for the SPECA backend.
//
// Conventions:
//   - paths are joined under `/api`, regardless of whether the caller writes
//     `health`, `/health`, or `runs/123`
//   - non-2xx responses throw an `ApiError` carrying status + body text so
//     callers can branch on `err.status === 404` without reparsing
//   - JSON is parsed eagerly for the common case; `init.headers` overrides
//     the default `Accept: application/json` if a route needs raw bytes

export class ApiError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const normalized = path.replace(/^\/+/, "");
  const url = `/api/${normalized}`;

  const headers = new Headers(init?.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(url, { ...init, headers });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body);
  }

  // Some endpoints (e.g. SSE) won't return JSON; callers should reach for
  // `fetch` directly in that case. For the common JSON path we parse here.
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.text()) as unknown as T;
}
