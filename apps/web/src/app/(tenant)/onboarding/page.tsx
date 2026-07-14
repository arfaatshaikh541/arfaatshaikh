"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { inviteMemberSchema, type InviteMemberInput } from "@leadflow/shared-types";
import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";
import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import type { ServiceOut } from "@/lib/types";

interface TenantOut {
  id: string;
  slug: string;
  name: string;
  public_key: string;
}

interface BusinessHoursWindow {
  start: string;
  end: string;
}

type BusinessHours = Record<string, BusinessHoursWindow | null>;

interface TenantSettingsOut {
  business_hours: BusinessHours;
  onboarding_completed_at: string | null;
}

interface RoleOut {
  id: string;
  name: string;
  slug: string;
}

const WEEKDAYS: [string, string][] = [
  ["mon", "Monday"],
  ["tue", "Tuesday"],
  ["wed", "Wednesday"],
  ["thu", "Thursday"],
  ["fri", "Friday"],
  ["sat", "Saturday"],
  ["sun", "Sunday"],
];

const DEFAULT_WINDOW: BusinessHoursWindow = { start: "09:00", end: "18:00" };

const STEPS = ["welcome", "services", "hours", "team", "done"] as const;
type Step = (typeof STEPS)[number];

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const { tenantId } = useCurrentTenant();
  const [stepIndex, setStepIndex] = useState(0);
  const step: Step = STEPS[stepIndex] ?? "welcome";

  const tenantQuery = useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => apiFetch<TenantOut>("/tenants/me"),
    enabled: Boolean(tenantId),
  });

  const servicesQuery = useQuery({
    queryKey: ["services", tenantId],
    queryFn: () => apiFetch<ServiceOut[]>("/tenants/me/services"),
    enabled: Boolean(tenantId) && step === "services",
  });

  const settingsQuery = useQuery({
    queryKey: ["tenant-settings", tenantId],
    queryFn: () => apiFetch<TenantSettingsOut>("/tenants/me/settings"),
    enabled: Boolean(tenantId),
  });

  const rolesQuery = useQuery({
    queryKey: ["roles", tenantId],
    queryFn: () => apiFetch<RoleOut[]>("/tenants/me/roles"),
    enabled: Boolean(tenantId) && step === "team",
  });

  const [businessHours, setBusinessHours] = useState<BusinessHours>({});
  useEffect(() => {
    if (settingsQuery.data) setBusinessHours(settingsQuery.data.business_hours ?? {});
  }, [settingsQuery.data]);

  useEffect(() => {
    if (settingsQuery.data?.onboarding_completed_at) {
      router.replace("/dashboard");
    }
  }, [router, settingsQuery.data]);

  const goNext = () => setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));

  const hoursMutation = useMutation({
    mutationFn: () =>
      apiFetch<TenantSettingsOut>("/tenants/me/settings", {
        method: "PATCH",
        body: { business_hours: businessHours },
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["tenant-settings", tenantId], data);
      goNext();
    },
  });

  const [inviteError, setInviteError] = useState<string | null>(null);
  const [invitedEmails, setInvitedEmails] = useState<string[]>([]);
  const {
    register: registerInvite,
    handleSubmit: handleInviteSubmit,
    reset: resetInvite,
    formState: { errors: inviteErrors, isSubmitting: isInviting },
  } = useForm<InviteMemberInput>({ resolver: zodResolver(inviteMemberSchema) });

  const inviteMutation = useMutation({
    mutationFn: (values: InviteMemberInput) =>
      apiFetch("/tenants/me/invitations", {
        method: "POST",
        body: { email: values.email, role_id: values.roleId },
      }),
    onSuccess: (_data, values) => {
      setInvitedEmails((prev) => [...prev, values.email]);
      resetInvite({ email: "", roleId: "" });
      queryClient.invalidateQueries({ queryKey: ["invitations", tenantId] });
    },
    onError: (err) => setInviteError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const completeMutation = useMutation({
    mutationFn: () =>
      apiFetch<TenantSettingsOut>("/tenants/me/onboarding/complete", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-settings", tenantId] });
      router.push("/dashboard");
    },
  });

  if (!tenantId) {
    return <p className="text-sm text-surface-400">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div
            key={s}
            className={
              "h-1.5 flex-1 rounded-full " + (i <= stepIndex ? "bg-accent-500" : "bg-surface-800")
            }
          />
        ))}
      </div>

      {step === "welcome" ? (
        <Card>
          <h1 className="mb-2 text-xl font-semibold text-surface-50">
            Welcome, {user?.first_name ?? "there"}
          </h1>
          <p className="mb-6 text-sm text-surface-400">
            {tenantQuery.data?.name ?? "Your workspace"} is ready. We&apos;ve already set up default
            pipeline stages, services and a lead-scoring workflow so you can start capturing leads
            right away. Let&apos;s finish a few quick steps to tailor it to your business.
          </p>
          <Button onClick={goNext}>Get started</Button>
        </Card>
      ) : null}

      {step === "services" ? (
        <Card>
          <h1 className="mb-2 text-xl font-semibold text-surface-50">Your services</h1>
          <p className="mb-4 text-sm text-surface-400">
            We seeded a starter list of professional services. Leads and the public enquiry form use
            these — you can rename, add or deactivate any of them later from Services.
          </p>
          {servicesQuery.isLoading ? (
            <p className="text-sm text-surface-400">Loading…</p>
          ) : (
            <ul className="mb-6 flex flex-wrap gap-2">
              {(servicesQuery.data ?? []).map((service) => (
                <li key={service.id}>
                  <Badge tone="accent">{service.name}</Badge>
                </li>
              ))}
            </ul>
          )}
          <Button onClick={goNext}>Next</Button>
        </Card>
      ) : null}

      {step === "hours" ? (
        <Card>
          <h1 className="mb-2 text-xl font-semibold text-surface-50">Business hours</h1>
          <p className="mb-4 text-sm text-surface-400">
            Drives available appointment slots for booking. You can change these any time in
            Settings.
          </p>
          <div className="mb-6 space-y-2">
            {WEEKDAYS.map(([key, label]) => {
              const window = businessHours[key] ?? null;
              const isOpen = window !== null;
              return (
                <div key={key} className="flex items-center gap-3">
                  <label className="flex w-32 items-center gap-2 text-sm text-surface-300">
                    <input
                      type="checkbox"
                      checked={isOpen}
                      onChange={(e) =>
                        setBusinessHours((prev) => ({
                          ...prev,
                          [key]: e.target.checked ? DEFAULT_WINDOW : null,
                        }))
                      }
                    />
                    {label}
                  </label>
                  {isOpen ? (
                    <>
                      <Input
                        type="time"
                        className="w-32"
                        value={window.start}
                        onChange={(e) =>
                          setBusinessHours((prev) => ({
                            ...prev,
                            [key]: { start: e.target.value, end: window.end },
                          }))
                        }
                      />
                      <span className="text-surface-500">to</span>
                      <Input
                        type="time"
                        className="w-32"
                        value={window.end}
                        onChange={(e) =>
                          setBusinessHours((prev) => ({
                            ...prev,
                            [key]: { start: window.start, end: e.target.value },
                          }))
                        }
                      />
                    </>
                  ) : (
                    <span className="text-sm text-surface-500">Closed</span>
                  )}
                </div>
              );
            })}
          </div>
          <div className="flex gap-2">
            <Button loading={hoursMutation.isPending} onClick={() => hoursMutation.mutate()}>
              Save and continue
            </Button>
            <Button variant="ghost" onClick={goNext}>
              Skip for now
            </Button>
          </div>
        </Card>
      ) : null}

      {step === "team" ? (
        <Card>
          <h1 className="mb-2 text-xl font-semibold text-surface-50">Invite your team</h1>
          <p className="mb-4 text-sm text-surface-400">
            Optional — you can always invite people later from Team.
          </p>
          {inviteError ? (
            <Alert tone="error" className="mb-4">
              {inviteError}
            </Alert>
          ) : null}
          {invitedEmails.length > 0 ? (
            <Alert tone="success" className="mb-4">
              Invited: {invitedEmails.join(", ")}
            </Alert>
          ) : null}
          <form
            onSubmit={handleInviteSubmit((values) => {
              setInviteError(null);
              inviteMutation.mutate(values);
            })}
            noValidate
            className="mb-6"
          >
            <div className="mb-3 grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="invite-email">Email</Label>
                <Input id="invite-email" type="email" {...registerInvite("email")} />
                <FormError message={inviteErrors.email?.message} />
              </div>
              <div>
                <Label htmlFor="invite-role">Role</Label>
                <select
                  id="invite-role"
                  className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50 focus:outline-none focus:ring-2 focus:ring-accent-500"
                  {...registerInvite("roleId")}
                >
                  <option value="">Select a role</option>
                  {(rolesQuery.data ?? []).map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
                <FormError message={inviteErrors.roleId?.message} />
              </div>
            </div>
            <Button type="submit" variant="secondary" loading={isInviting}>
              Send invite
            </Button>
          </form>
          <div className="flex gap-2">
            <Button onClick={goNext}>Next</Button>
            <Button variant="ghost" onClick={goNext}>
              Skip for now
            </Button>
          </div>
        </Card>
      ) : null}

      {step === "done" ? (
        <Card>
          <h1 className="mb-2 text-xl font-semibold text-surface-50">You&apos;re all set</h1>
          <p className="mb-6 text-sm text-surface-400">
            Your workspace is ready. Head to the dashboard to see your pipeline, or share your
            public enquiry form to start capturing leads.
          </p>
          <Button loading={completeMutation.isPending} onClick={() => completeMutation.mutate()}>
            Go to dashboard
          </Button>
        </Card>
      ) : null}
    </div>
  );
}
