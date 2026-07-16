"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Card, CardHeader, FormRoot, SeverityBadge, StatusBadge, TextInput } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { IncidentListItem } from "@/lib/types";

const STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  declared: "warning",
  investigating: "warning",
  contained: "neutral",
  resolved: "positive",
  closed: "positive",
};

const declareSchema = z.object({
  title: z.string().min(2, "Give the incident a title."),
  description: z.string().optional(),
  severity: z.string().min(1, "Choose a severity."),
});
type DeclareFormValues = z.infer<typeof declareSchema>;

export default function IncidentsPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const canDeclare = hasPermission("incidents.declare");
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [declareError, setDeclareError] = useState<string | null>(null);
  const [showDeclareForm, setShowDeclareForm] = useState(false);

  const incidentsQuery = useQuery({
    queryKey: ["incidents", { status, severity }],
    queryFn: () =>
      apiClient.get<IncidentListItem[]>("/api/incidents", {
        ...(status ? { status } : {}),
        ...(severity ? { severity } : {}),
      }),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<DeclareFormValues>({ resolver: zodResolver(declareSchema) });

  const onDeclare = async (values: DeclareFormValues) => {
    setDeclareError(null);
    try {
      await apiClient.post("/api/incidents", values);
      reset();
      setShowDeclareForm(false);
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
    } catch (err) {
      setDeclareError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Incidents</h1>
          <p className="text-sm text-ink-500">
            Coordinate the response to a security event across the findings and assets it involves.
          </p>
        </div>
        {canDeclare ? (
          <Button variant="secondary" onClick={() => setShowDeclareForm((v) => !v)} className="shrink-0">
            Declare incident
          </Button>
        ) : null}
      </div>

      {showDeclareForm ? (
        <Card>
          <CardHeader title="Declare a new incident" />
          <FormRoot onSubmit={handleSubmit(onDeclare)} className="max-w-xl">
            {declareError ? <Alert tone="error">{declareError}</Alert> : null}
            <TextInput label="Title" error={errors.title?.message} {...register("title")} />
            <div className="flex flex-col gap-1.5">
              <label htmlFor="description" className="text-sm font-medium text-ink-700">
                Description
              </label>
              <textarea
                id="description"
                rows={3}
                className="rounded border border-surface-border bg-surface-800 px-3 py-2 text-sm text-ink-900"
                {...register("description")}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="severity" className="text-sm font-medium text-ink-700">
                Severity
              </label>
              <select
                id="severity"
                className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                {...register("severity")}
              >
                <option value="">Select a severity</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              {errors.severity ? <p className="text-xs text-severity-critical">{errors.severity.message}</p> : null}
            </div>
            <Button type="submit" isLoading={isSubmitting}>
              Declare
            </Button>
          </FormRoot>
        </Card>
      ) : null}

      <Card>
        <div className="flex flex-wrap gap-3">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          >
            <option value="">All statuses</option>
            <option value="declared">Declared</option>
            <option value="investigating">Investigating</option>
            <option value="contained">Contained</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          >
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </Card>

      <Card>
        <CardHeader title={`Incidents${incidentsQuery.data ? ` (${incidentsQuery.data.length})` : ""}`} />
        {incidentsQuery.data && incidentsQuery.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">Title</th>
                  <th className="py-2 pr-4 font-medium">Severity</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Findings</th>
                  <th className="py-2 pr-4 font-medium">Assets</th>
                  <th className="py-2 font-medium">Declared</th>
                </tr>
              </thead>
              <tbody>
                {incidentsQuery.data.map((incident) => (
                  <tr key={incident.id} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 text-ink-900">
                      <Link href={`/incidents/${incident.id}`} className="hover:underline">
                        {incident.title}
                      </Link>
                    </td>
                    <td className="py-2 pr-4">
                      <SeverityBadge severity={incident.severity as "critical" | "high" | "medium" | "low"} />
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge label={incident.status} tone={STATUS_TONE[incident.status] ?? "neutral"} />
                    </td>
                    <td className="py-2 pr-4 text-ink-500">{incident.finding_count}</td>
                    <td className="py-2 pr-4 text-ink-500">{incident.asset_count}</td>
                    <td className="py-2 text-ink-500">{new Date(incident.declared_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500">No incidents declared yet.</p>
        )}
      </Card>
    </div>
  );
}
