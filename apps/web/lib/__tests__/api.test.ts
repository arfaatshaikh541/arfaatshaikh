import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError } from "../api";

describe("api client", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("throws ApiError with code/message/fields on a structured error response", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "VALIDATION_ERROR", message: "bad input", fields: { email: "invalid" } },
        }),
        { status: 400, headers: { "content-type": "application/json" } }
      )
    ) as unknown as typeof fetch;

    await expect(api.get("/api/v1/whatever")).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(400);
      expect(apiErr.code).toBe("VALIDATION_ERROR");
      expect(apiErr.message).toBe("bad input");
      expect(apiErr.fields).toEqual({ email: "invalid" });
      return true;
    });
  });

  it("resolves with the parsed JSON body on success", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    ) as unknown as typeof fetch;

    const result = await api.get<{ status: string }>("/healthz");
    expect(result.status).toBe("ok");
  });

  beforeEach(() => {
    document.cookie = "";
  });

  it("attaches X-CSRF-Token header on mutating requests when the csrf cookie is present", async () => {
    document.cookie = "gridkeep_csrf=test-token-value";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200, headers: { "content-type": "application/json" } })
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    await api.post("/api/v1/auth/login", { email: "a@b.com", password: "x" });

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get("X-CSRF-Token")).toBe("test-token-value");
  });
});
