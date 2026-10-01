import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, setCsrfToken } from "./api";
afterEach(()=>{vi.unstubAllGlobals();setCsrfToken(null)});
describe("apiFetch",()=>{it("sends credentials and CSRF on writes",async()=>{const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({ok:true}),{status:200,headers:{"Content-Type":"application/json"}}));vi.stubGlobal("fetch",fetchMock);setCsrfToken("csrf");await apiFetch("/test",{method:"POST",body:"{}"});const init=fetchMock.mock.calls[0][1] as RequestInit;expect(init.credentials).toBe("include");expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf")})});

describe("apiFetch CSRF refresh", () => {
  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  it("fetches the current token and retries a write once when another tab rotated it", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json(403, { error: { code: "csrf_failed", message: "CSRF validation failed." } }))
      .mockResolvedValueOnce(json(200, { csrf_token: "fresh" }))
      .mockResolvedValueOnce(json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock); setCsrfToken("stale");
    await expect(apiFetch("/admin/x", { method: "POST", body: "{}" })).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(new Headers((fetchMock.mock.calls[2][1] as RequestInit).headers).get("X-CSRF-Token")).toBe("fresh");
  });
  it("does not retry reads, other 403s, or a second CSRF failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(403, { error: { code: "forbidden", message: "No." } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("/admin/x", { method: "POST", body: "{}" })).rejects.toMatchObject({ status: 403, code: "forbidden" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const again = vi.fn().mockResolvedValueOnce(json(403, { error: { code: "csrf_failed", message: "x" } })).mockResolvedValueOnce(json(200, { csrf_token: "t" })).mockResolvedValueOnce(json(403, { error: { code: "csrf_failed", message: "x" } }));
    vi.stubGlobal("fetch", again);
    await expect(apiFetch("/admin/x", { method: "POST", body: "{}" })).rejects.toMatchObject({ code: "csrf_failed" });
    expect(again).toHaveBeenCalledTimes(3);
  });
});
