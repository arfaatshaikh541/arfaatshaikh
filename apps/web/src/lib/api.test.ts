import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, setCsrfToken } from "./api";
afterEach(()=>{vi.unstubAllGlobals();setCsrfToken(null)});
describe("apiFetch",()=>{it("sends credentials and CSRF on writes",async()=>{const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({ok:true}),{status:200,headers:{"Content-Type":"application/json"}}));vi.stubGlobal("fetch",fetchMock);setCsrfToken("csrf");await apiFetch("/test",{method:"POST",body:"{}"});const init=fetchMock.mock.calls[0][1] as RequestInit;expect(init.credentials).toBe("include");expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf")})});
