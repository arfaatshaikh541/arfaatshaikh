import { z } from "zod";

/**
 * Schemas shared between frontend surfaces (and mirrored by the backend's
 * Pydantic schemas in apps/api/app/schemas). Keeping these in one workspace
 * package means a new admin/mobile client can reuse the same client-side
 * validation instead of re-deriving it from the OpenAPI spec by hand.
 */

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, "Password is required"),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const forgotPasswordSchema = z.object({
  email: z.string().email(),
});
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    token: z.string().min(1),
    newPassword: z.string().min(10, "Must be at least 10 characters"),
    confirmPassword: z.string().min(10),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;

export const acceptInvitationSchema = z
  .object({
    token: z.string().min(1),
    firstName: z.string().min(1, "First name is required"),
    lastName: z.string().min(1, "Last name is required"),
    password: z.string().min(10, "Must be at least 10 characters"),
    confirmPassword: z.string().min(10),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });
export type AcceptInvitationInput = z.infer<typeof acceptInvitationSchema>;

export const signupSchema = z
  .object({
    name: z.string().min(2, "Must be at least 2 characters").max(200),
    slug: z
      .string()
      .min(2, "Must be at least 2 characters")
      .max(80)
      .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens only"),
    ownerFirstName: z.string().min(1, "First name is required").max(100),
    ownerLastName: z.string().min(1, "Last name is required").max(100),
    ownerEmail: z.string().email(),
    ownerPassword: z.string().min(10, "Must be at least 10 characters").max(200),
    confirmPassword: z.string().min(10),
  })
  .refine((data) => data.ownerPassword === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });
export type SignupInput = z.infer<typeof signupSchema>;

const hexColor = z
  .string()
  .regex(/^#[0-9A-Fa-f]{6}$/, "Must be a hex color like #F97316");

export const tenantSettingsSchema = z.object({
  logoUrl: z.string().url().optional().or(z.literal("")),
  brandPrimaryColor: hexColor,
  brandSecondaryColor: hexColor,
  contactEmail: z.string().email().optional().or(z.literal("")),
  contactPhone: z.string().optional(),
  locale: z.string().min(2),
  dataRetentionDays: z.number().int().min(1).max(3650),
  privacyText: z.string().optional(),
});
export type TenantSettingsInput = z.infer<typeof tenantSettingsSchema>;

export const inviteMemberSchema = z.object({
  email: z.string().email(),
  roleId: z.string().uuid(),
});
export type InviteMemberInput = z.infer<typeof inviteMemberSchema>;

// These mirror the raw JSON shape returned by the FastAPI backend
// (apps/api/app/schemas), which is snake_case throughout and is consumed
// as-is by the frontend rather than transformed to camelCase - see how
// apps/web reads e.g. `settings.brand_primary_color` directly.
export interface RoleSummary {
  id: string;
  name: string;
  slug: string;
  is_system: boolean;
  permissions: { code: string; description: string }[];
}

export interface MembershipSummary {
  tenant_id: string;
  tenant_slug: string;
  tenant_name: string;
  role: RoleSummary;
  status: "active" | "invited" | "suspended";
}

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_platform_super_admin: boolean;
  email_verified: boolean;
  memberships: MembershipSummary[];
}
