"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Banner, Button, Card, TextField } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError, api } from "@/lib/api";
import type { Campaign, CreateCampaignRequest } from "@/lib/types";

const NUMBER_PATTERN = /^-?\d+(\.\d+)?$/;

const createCampaignSchema = z.object({
  name: z.string().min(1, "Name is required.").max(200),
  result_limit: z
    .string()
    .min(1, "Required.")
    .refine((v) => NUMBER_PATTERN.test(v) && Number.isInteger(Number(v)), "Must be a whole number.")
    .refine((v) => Number(v) >= 1 && Number(v) <= 5000, "Must be between 1 and 5000."),
  industry: z.string().min(1, "Industry is required."),
  category: z.string().optional(),
  country: z.string().min(1, "Country is required."),
  city: z.string().min(1, "City is required."),
  area: z.string().optional(),
  min_rating: z
    .string()
    .optional()
    .refine((v) => !v || (NUMBER_PATTERN.test(v) && Number(v) >= 0 && Number(v) <= 5), "Must be 0-5."),
  min_reviews: z
    .string()
    .optional()
    .refine((v) => !v || (NUMBER_PATTERN.test(v) && Number.isInteger(Number(v)) && Number(v) >= 0), "Must be a whole number."),
  must_have_phone: z.boolean(),
  website_requirement: z.enum(["any", "required", "missing"]),
});

type CreateCampaignFormValues = z.infer<typeof createCampaignSchema>;

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  estimating: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  ready: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
  queued: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
  running: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  pausing: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  paused: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  cancelling: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  cancelled: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  completed: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  partially_completed: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
        STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
      }`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

export default function CampaignsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const campaignsQuery = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn: () => api.get<Campaign[]>("/campaigns"),
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateCampaignFormValues>({
    resolver: zodResolver(createCampaignSchema),
    defaultValues: {
      must_have_phone: false,
      website_requirement: "any",
    },
  });

  const onSubmit = async (values: CreateCampaignFormValues) => {
    setFormError(null);
    try {
      const payload: CreateCampaignRequest = {
        name: values.name,
        source_key: "mock",
        result_limit: Number(values.result_limit),
        industry: values.industry,
        category: values.category || null,
        country: values.country,
        city: values.city,
        area: values.area || null,
        min_rating: values.min_rating ? Number(values.min_rating) : null,
        min_reviews: values.min_reviews ? Number(values.min_reviews) : null,
        must_have_phone: values.must_have_phone,
        website_requirement: values.website_requirement,
      };
      const campaign = await api.post<Campaign>("/campaigns", payload);
      // Estimating is free (no credits reserved yet) and is always the next
      // required step before a campaign can be launched, so do it
      // immediately rather than making the user click twice.
      await api.post(`/campaigns/${campaign.id}/estimate`);
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      router.push(`/campaigns/${campaign.id}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create the campaign.");
    }
  };

  const canCreate = !campaignsQuery.isError;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Campaigns</h1>
        {canCreate && (
          <Button variant={showForm ? "secondary" : "primary"} onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "New campaign"}
          </Button>
        )}
      </div>

      {campaignsQuery.isError && (
        <Banner tone="info">You don&apos;t have permission to view campaigns.</Banner>
      )}

      {showForm && (
        <Card>
          <h2 className="mb-4 text-lg font-medium">New campaign</h2>
          <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
            Uses the <strong>mock</strong> connector, which returns deterministic sample business
            records for testing - not real lead data.
          </p>
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TextField label="Campaign name" error={errors.name?.message} {...register("name")} />
            <TextField
              label="Result limit"
              type="number"
              hint="1 credit per business found, up to this many results."
              error={errors.result_limit?.message}
              {...register("result_limit")}
            />
            <TextField label="Industry" error={errors.industry?.message} {...register("industry")} />
            <TextField label="Category (optional)" error={errors.category?.message} {...register("category")} />
            <TextField label="Country" error={errors.country?.message} {...register("country")} />
            <TextField label="City" error={errors.city?.message} {...register("city")} />
            <TextField label="Area (optional)" error={errors.area?.message} {...register("area")} />
            <TextField
              label="Minimum rating (optional)"
              type="number"
              step="0.1"
              min="0"
              max="5"
              error={errors.min_rating?.message}
              {...register("min_rating")}
            />
            <TextField
              label="Minimum reviews (optional)"
              type="number"
              min="0"
              error={errors.min_reviews?.message}
              {...register("min_reviews")}
            />
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                Website requirement
              </label>
              <select
                {...register("website_requirement")}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                <option value="any">Any</option>
                <option value="required">Must have a website</option>
                <option value="missing">Must not have a website</option>
              </select>
            </div>
            <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-700 dark:text-slate-200">
              <input type="checkbox" {...register("must_have_phone")} className="h-4 w-4 rounded border-slate-300" />
              Must have a phone number
            </label>
            <div className="sm:col-span-2">
              <Button type="submit" isLoading={isSubmitting}>
                Create &amp; estimate
              </Button>
            </div>
          </form>
          {formError && (
            <div className="mt-4">
              <Banner tone="error">{formError}</Banner>
            </div>
          )}
        </Card>
      )}

      <Card>
        {campaignsQuery.data && campaignsQuery.data.length > 0 ? (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Result limit</th>
                <th className="py-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {campaignsQuery.data.map((campaign) => (
                <tr key={campaign.id}>
                  <td className="py-2">
                    <Link
                      href={`/campaigns/${campaign.id}`}
                      className="font-medium text-brand-700 hover:underline dark:text-brand-400"
                    >
                      {campaign.name}
                    </Link>
                  </td>
                  <td className="py-2">
                    <StatusBadge status={campaign.status} />
                  </td>
                  <td className="py-2 text-slate-500 dark:text-slate-400">{campaign.result_limit}</td>
                  <td className="py-2 text-slate-500 dark:text-slate-400">
                    {new Date(campaign.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          !campaignsQuery.isError && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              No campaigns yet. Create one to start discovering leads.
            </p>
          )
        )}
      </Card>
    </div>
  );
}
