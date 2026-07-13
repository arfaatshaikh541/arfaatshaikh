const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  const value = match?.[1];
  return value ? decodeURIComponent(value) : null;
}

export function getCurrentTenantId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("leadflow.currentTenantId");
}

export function setCurrentTenantId(tenantId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem("leadflow.currentTenantId", tenantId);
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  withTenant?: boolean;
  headers?: Record<string, string>;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, withTenant = true } = options;
  const headers: Record<string, string> = { ...options.headers };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (method !== "GET") {
    const csrfToken = readCookie("csrf_token");
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }
  if (withTenant) {
    const tenantId = getCurrentTenantId();
    if (tenantId) headers["X-Tenant-Id"] = tenantId;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : undefined;

  if (!response.ok) {
    const message =
      (data && typeof data === "object" && "detail" in data && typeof data.detail === "string"
        ? data.detail
        : undefined) ?? `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message);
  }

  return data as T;
}
