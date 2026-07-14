import { describe, expect, it } from "vitest";

import {
  loginSchema,
  resetPasswordSchema,
  signupSchema,
  tenantSettingsSchema,
} from "@leadflow/shared-types";

describe("loginSchema", () => {
  it("accepts a valid email/password", () => {
    const result = loginSchema.safeParse({ email: "owner@example.com", password: "hunter2" });
    expect(result.success).toBe(true);
  });

  it("rejects an invalid email", () => {
    const result = loginSchema.safeParse({ email: "not-an-email", password: "hunter2" });
    expect(result.success).toBe(false);
  });

  it("rejects an empty password", () => {
    const result = loginSchema.safeParse({ email: "owner@example.com", password: "" });
    expect(result.success).toBe(false);
  });
});

describe("resetPasswordSchema", () => {
  it("rejects mismatched passwords", () => {
    const result = resetPasswordSchema.safeParse({
      token: "abc",
      newPassword: "SomeLongPassword1",
      confirmPassword: "Different1234567",
    });
    expect(result.success).toBe(false);
  });

  it("accepts matching, long-enough passwords", () => {
    const result = resetPasswordSchema.safeParse({
      token: "abc",
      newPassword: "SomeLongPassword1",
      confirmPassword: "SomeLongPassword1",
    });
    expect(result.success).toBe(true);
  });
});

describe("signupSchema", () => {
  const valid = {
    name: "Acme Consulting",
    slug: "acme-consulting",
    ownerFirstName: "Jane",
    ownerLastName: "Doe",
    ownerEmail: "jane@acme.example",
    ownerPassword: "SignupPassw0rd!123",
    confirmPassword: "SignupPassw0rd!123",
  };

  it("accepts a fully valid signup", () => {
    expect(signupSchema.safeParse(valid).success).toBe(true);
  });

  it("rejects an invalid slug", () => {
    const result = signupSchema.safeParse({ ...valid, slug: "Not A Slug!" });
    expect(result.success).toBe(false);
  });

  it("rejects mismatched passwords", () => {
    const result = signupSchema.safeParse({ ...valid, confirmPassword: "SomethingElse123" });
    expect(result.success).toBe(false);
  });

  it("rejects a short password", () => {
    const result = signupSchema.safeParse({ ...valid, ownerPassword: "short", confirmPassword: "short" });
    expect(result.success).toBe(false);
  });
});

describe("tenantSettingsSchema", () => {
  it("rejects a non-hex brand color", () => {
    const result = tenantSettingsSchema.safeParse({
      brandPrimaryColor: "orange",
      brandSecondaryColor: "#111827",
      locale: "en",
      dataRetentionDays: 365,
    });
    expect(result.success).toBe(false);
  });

  it("accepts valid hex colors", () => {
    const result = tenantSettingsSchema.safeParse({
      brandPrimaryColor: "#F97316",
      brandSecondaryColor: "#111827",
      locale: "en",
      dataRetentionDays: 365,
    });
    expect(result.success).toBe(true);
  });
});
