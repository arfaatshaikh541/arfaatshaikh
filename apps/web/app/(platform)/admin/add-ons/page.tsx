"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { PlatformAddOn, PlatformFeature } from "@/lib/types";

interface GrantRow {
  feature_code: string;
  limit: string;
}

function grantsFromRows(rows: GrantRow[], featuresByCode: Map<string, PlatformFeature>) {
  return {
    features: rows
      .filter((r) => r.feature_code)
      .map((r) => {
        const feature = featuresByCode.get(r.feature_code);
        const config = feature?.feature_type === "limit" && r.limit ? { limit: Number(r.limit) } : { enabled: true };
        return { feature_code: r.feature_code, config };
      }),
  };
}

function rowsFromGrants(grants: PlatformAddOn["grants"]): GrantRow[] {
  const rows = (grants?.features ?? []).map((f) => ({
    feature_code: f.feature_code,
    limit: typeof f.config?.limit === "number" ? String(f.config.limit) : "",
  }));
  return rows.length > 0 ? rows : [{ feature_code: "", limit: "" }];
}

function GrantRowsEditor({ rows, setRows, features }: { rows: GrantRow[]; setRows: (rows: GrantRow[]) => void; features: PlatformFeature[] }) {
  return (
    <div className="space-y-2">
      {rows.map((row, index) => (
        <div key={index} className="flex flex-wrap items-center gap-2">
          <select
            className="focus-ring min-w-[220px] flex-1 rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
            value={row.feature_code}
            onChange={(e) => setRows(rows.map((r, i) => (i === index ? { ...r, feature_code: e.target.value } : r)))}
          >
            <option value="">Select a feature…</option>
            {features.map((f) => (
              <option key={f.id} value={f.code}>
                {f.module_code} · {f.name} ({f.feature_type})
              </option>
            ))}
          </select>
          <Input
            className="w-32"
            placeholder="limit (optional)"
            value={row.limit}
            onChange={(e) => setRows(rows.map((r, i) => (i === index ? { ...r, limit: e.target.value } : r)))}
          />
          <Button type="button" variant="secondary" onClick={() => setRows(rows.filter((_, i) => i !== index))} disabled={rows.length === 1}>
            Remove
          </Button>
        </div>
      ))}
      <Button type="button" variant="secondary" onClick={() => setRows([...rows, { feature_code: "", limit: "" }])}>
        Add grant
      </Button>
    </div>
  );
}

function AddOnCard({ addOn, features }: { addOn: PlatformAddOn; features: PlatformFeature[] }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(addOn.name);
  const [rows, setRows] = useState<GrantRow[]>(() => rowsFromGrants(addOn.grants));
  const featuresByCode = new Map(features.map((f) => [f.code, f]));

  const updateMutation = useMutation({
    mutationFn: () => api.put(`/platform/add-ons/${addOn.id}`, { name, grants: grantsFromRows(rows, featuresByCode) }),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["platform", "add-ons"] });
    },
  });

  if (!editing) {
    return (
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink">{addOn.name}</h2>
            <p className="mt-1 text-xs text-ink-faint">code: {addOn.code}</p>
            <ul className="mt-2 space-y-1">
              {addOn.grants.features?.map((g) => (
                <li key={g.feature_code} className="text-xs text-ink-muted">
                  {g.feature_code}: {JSON.stringify(g.config)}
                </li>
              ))}
              {(!addOn.grants.features || addOn.grants.features.length === 0) && <li className="text-xs text-ink-faint">No grants configured.</li>}
            </ul>
          </div>
          <Button variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="space-y-3">
        {updateMutation.isError && (
          <Alert tone="error">{updateMutation.error instanceof ApiError ? updateMutation.error.message : "Update failed."}</Alert>
        )}
        <div>
          <Label htmlFor={`addon-name-${addOn.id}`}>Name</Label>
          <Input id={`addon-name-${addOn.id}`} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label>Grants</Label>
          <GrantRowsEditor rows={rows} setRows={setRows} features={features} />
        </div>
        <div className="flex gap-2">
          <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending || !name.trim()}>
            Save
          </Button>
          <Button variant="secondary" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function AddOnsPage() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [rows, setRows] = useState<GrantRow[]>([{ feature_code: "", limit: "" }]);

  const addOnsQuery = useQuery({ queryKey: ["platform", "add-ons"], queryFn: () => api.get<PlatformAddOn[]>("/platform/add-ons") });
  const featuresQuery = useQuery({ queryKey: ["platform", "features"], queryFn: () => api.get<PlatformFeature[]>("/platform/features") });
  const featuresByCode = new Map((featuresQuery.data ?? []).map((f) => [f.code, f]));

  const createMutation = useMutation({
    mutationFn: () => api.post("/platform/add-ons", { code, name, grants: grantsFromRows(rows, featuresByCode) }),
    onSuccess: () => {
      setCode("");
      setName("");
      setRows([{ feature_code: "", limit: "" }]);
      queryClient.invalidateQueries({ queryKey: ["platform", "add-ons"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Add-ons</h1>
        <p className="mt-1 text-sm text-ink-muted">Extra grants a tenant can be given on top of their plan (e.g. extra storage).</p>
      </div>

      <Card>
        <CardHeader title="Add an add-on" />
        {createMutation.isError && (
          <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Could not create add-on."}</Alert>
        )}
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[160px] flex-1">
              <Label htmlFor="new-addon-code">Code</Label>
              <Input id="new-addon-code" placeholder="e.g. extra_storage" value={code} onChange={(e) => setCode(e.target.value)} required />
            </div>
            <div className="min-w-[200px] flex-1">
              <Label htmlFor="new-addon-name">Name</Label>
              <Input id="new-addon-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
          </div>
          <div>
            <Label>Grants</Label>
            <GrantRowsEditor rows={rows} setRows={setRows} features={featuresQuery.data ?? []} />
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            Create
          </Button>
        </form>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {addOnsQuery.data?.map((addOn) => (
          <AddOnCard key={addOn.id} addOn={addOn} features={featuresQuery.data ?? []} />
        ))}
      </div>
    </div>
  );
}
