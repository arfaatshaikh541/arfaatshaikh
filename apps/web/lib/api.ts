/**
 * Thin fetch wrapper for the GRIDKEEP API.
 *
 * - `credentials: "include"` so the HttpOnly session cookie set by the API
 *   is sent on every request (the API and web app are same-site, so
 *   SameSite=Lax cookies flow across the port difference automatically).
 * - Reads the non-HttpOnly CSRF cookie and echoes it in the `X-CSRF-Token`
 *   header on every mutating request, per the API's double-submit check.
 * - Never stores or forwards a tenant_id chosen by the caller for
 *   authorization - the server derives tenant context from the session
 *   itself. Any `tenantId` accepted here is purely a UI-selection value
 *   (e.g. "switch to this tenant"), re-verified server-side.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  requestId?: string;

  constructor(message: string, code: string, status: number, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  const value = match?.[1];
  return value !== undefined ? decodeURIComponent(value) : null;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (method !== "GET") {
    const csrfToken = readCookie("gridkeep_csrf");
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorBody = data?.error ?? { code: "unknown_error", message: "An unexpected error occurred." };
    throw new ApiError(errorBody.message, errorBody.code, response.status, errorBody.request_id);
  }

  return data as T;
}

export const api = {
  get: <T>(path: string) => apiRequest<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: "DELETE" }),
};
