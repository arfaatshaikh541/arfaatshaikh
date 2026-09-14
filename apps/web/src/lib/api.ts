import type { ApiErrorBody } from "@world-of-islam/shared-types";

// The public API origin, e.g. "http://localhost:8000" locally or
// "https://app.arfaat.com/worldofislam" behind the production reverse proxy.
// Every request is versioned under /api/v1, which the FastAPI app mounts at
// its root - callers pass domain-relative paths ("/quran/...", "/auth/login")
// and never repeat "/api/v1" themselves.
const API_ORIGIN = process.env.NEXT_PUBLIC_WOI_API_ORIGIN ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";
let csrfToken: string | null = null;

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string) { super(message); }
}

export function setCsrfToken(token: string | null) { csrfToken = token; }
export function getCsrfToken() { return csrfToken; }

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (csrfToken && !["GET", "HEAD", "OPTIONS"].includes((init.method ?? "GET").toUpperCase())) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(`${API_ORIGIN}${API_PREFIX}${path}`, { ...init, headers, credentials: "include", cache: "no-store" });
  const body = response.status === 204 ? null : await response.json().catch(() => null) as ApiErrorBody | T | null;
  if (!response.ok) {
    const error = (body ?? {}) as ApiErrorBody;
    const code = error.error?.code ?? error.code ?? "request_failed";
    const message = error.error?.message ?? error.message ?? error.detail ?? "The request could not be completed.";
    throw new ApiError(response.status, code, message);
  }
  return body as T;
}
