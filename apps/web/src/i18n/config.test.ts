import { describe, expect, it } from "vitest";
import { direction, isLocale } from "./config";
describe("locale foundation",()=>{it("uses RTL for Arabic",()=>expect(direction("ar")).toBe("rtl"));it("rejects unsupported locales",()=>expect(isLocale("xx")).toBe(false));});
