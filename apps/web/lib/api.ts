// Thin fetch client for the GRIDKEEP control-api. All requests go through
// the browser's cookie jar (credentials: "include") -- the frontend never
// holds a session token or any secret itself. State-changing requests echo
// back the non-HttpOnly CSRF cookie in the X-CSRF-Token header, matching
// the control-api's double-submit-cookie CSRF protection.

const API_BASE = process.env.NEXT_PUBLIC_CONTROL_API_URL ?? "http://localhost:8080";

export class ApiError extends Error {
  code: string;
  status: number;
  fields?: Record<string, string>;

  constructor(status: number, code: string, message: string, fields?: Record<string, string>) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");

  if (method !== "GET" && method !== "HEAD") {
    const csrf = readCookie("gridkeep_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    credentials: "include",
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json().catch(() => undefined) : undefined;

  if (!res.ok) {
    const err = body?.error;
    throw new ApiError(res.status, err?.code ?? "UNKNOWN", err?.message ?? res.statusText, err?.fields);
  }

  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data !== undefined ? JSON.stringify(data) : undefined }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: data !== undefined ? JSON.stringify(data) : undefined }),
  warmCsrf: () => request<{ status: string }>("/healthz"),
};

export interface CurrentUser {
  user_id: string;
}

export interface EnterpriseMembership {
  id: string;
  user_id: string;
  enterprise_tenant_id: string;
  role_key: string;
  role_name: string;
  status: string;
  created_at: string;
}

export interface OperatorMembership {
  id: string;
  user_id: string;
  operator_id: string;
  role_key: string;
  role_name: string;
  status: string;
  created_at: string;
}

export interface EnterpriseTenant {
  id: string;
  legal_name: string;
  display_name: string;
  country: string;
  status: string;
  is_fictional_demo_data: boolean;
  created_at: string;
}
