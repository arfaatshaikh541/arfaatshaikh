"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { FeatureType, PlatformFeature, PlatformModule } from "@/lib/types";

function ModuleEditor({ module, features }: { module: PlatformModule; features: PlatformFeature[] }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(module.name);
  const [description, setDescription] = useState(module.description);
  const [addingFeature, setAddingFeature] = useState(false);
  const [featureCode, setFeatureCode] = useState("");
  const [featureName, setFeatureName] = useState("");
  const [featureType, setFeatureType] = useState<FeatureType>("boolean");
  const [editingFeatureId, setEditingFeatureId] = useState<string | null>(null);
  const [editingFeatureName, setEditingFeatureName] = useState("");

  const updateModuleMutation = useMutation({
    mutationFn: () => api.put(`/platform/modules/${module.id}`, { name, description }),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["platform", "modules"] });
    },
  });

  const createFeatureMutation = useMutation({
    mutationFn: () =>
      api.post("/platform/features", { module_id: module.id, code: featureCode, name: featureName, feature_type: featureType }),
    onSuccess: () => {
      setAddingFeature(false);
      setFeatureCode("");
      setFeatureName("");
      setFeatureType("boolean");
      queryClient.invalidateQueries({ queryKey: ["platform", "features"] });
    },
  });

  const updateFeatureMutation = useMutation({
    mutationFn: (featureId: string) => api.put(`/platform/features/${featureId}`, { name: editingFeatureName }),
    onSuccess: () => {
      setEditingFeatureId(null);
      queryClient.invalidateQueries({ queryKey: ["platform", "features"] });
    },
  });

  return (
    <Card>
      {editing ? (
        <div className="space-y-3">
          {updateModuleMutation.isError && (
            <Alert tone="error">{updateModuleMutation.error instanceof ApiError ? updateModuleMutation.error.message : "Update failed."}</Alert>
          )}
          <div>
            <Label htmlFor={`mod-name-${module.id}`}>Name</Label>
            <Input id={`mod-name-${module.id}`} value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor={`mod-desc-${module.id}`}>Description</Label>
            <Input id={`mod-desc-${module.id}`} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button onClick={() => updateModuleMutation.mutate()} disabled={updateModuleMutation.isPending || !name.trim()}>
              Save
            </Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-ink">{module.name}</p>
            <p className="mt-1 text-xs text-ink-faint">code: {module.code}</p>
            {module.description && <p className="mt-1 text-xs text-ink-muted">{module.description}</p>}
          </div>
          <Button variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
      )}

      <div className="mt-4 border-t border-surface-border pt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Features</p>
        <div className="mt-2 space-y-2">
          {features.map((feature) => (
            <div key={feature.id} className="flex items-center justify-between rounded-md border border-surface-border px-3 py-2 text-sm">
              {editingFeatureId === feature.id ? (
                <div className="flex flex-1 items-center gap-2">
                  <Input
                    className="flex-1"
                    value={editingFeatureName}
                    onChange={(e) => setEditingFeatureName(e.target.value)}
                  />
                  <Button onClick={() => updateFeatureMutation.mutate(feature.id)} disabled={updateFeatureMutation.isPending}>
                    Save
                  </Button>
                  <Button variant="secondary" onClick={() => setEditingFeatureId(null)}>
                    Cancel
                  </Button>
                </div>
              ) : (
                <>
                  <div>
                    <span className="text-ink">{feature.name}</span>
                    <span className="ml-2 text-xs text-ink-faint">
                      {feature.code} · {feature.feature_type}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEditingFeatureId(feature.id);
                      setEditingFeatureName(feature.name);
                    }}
                  >
                    Edit
                  </Button>
                </>
              )}
            </div>
          ))}
          {features.length === 0 && <p className="text-xs text-ink-faint">No features yet.</p>}
        </div>

        {addingFeature ? (
          <div className="mt-3 space-y-2 rounded-md border border-surface-border p-3">
            {createFeatureMutation.isError && (
              <Alert tone="error">{createFeatureMutation.error instanceof ApiError ? createFeatureMutation.error.message : "Could not create feature."}</Alert>
            )}
            <div className="flex flex-wrap gap-2">
              <Input className="min-w-[140px] flex-1" placeholder="code" value={featureCode} onChange={(e) => setFeatureCode(e.target.value)} />
              <Input className="min-w-[160px] flex-1" placeholder="Name" value={featureName} onChange={(e) => setFeatureName(e.target.value)} />
              <select
                className="focus-ring rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={featureType}
                onChange={(e) => setFeatureType(e.target.value as FeatureType)}
              >
                <option value="boolean">Boolean</option>
                <option value="limit">Limit</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => createFeatureMutation.mutate()}
                disabled={createFeatureMutation.isPending || !featureCode.trim() || !featureName.trim()}
              >
                Add feature
              </Button>
              <Button variant="secondary" onClick={() => setAddingFeature(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="secondary" className="mt-3" onClick={() => setAddingFeature(true)}>
            Add feature
          </Button>
        )}
      </div>
    </Card>
  );
}

export default function ModulesPage() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const modulesQuery = useQuery({ queryKey: ["platform", "modules"], queryFn: () => api.get<PlatformModule[]>("/platform/modules") });
  const featuresQuery = useQuery({ queryKey: ["platform", "features"], queryFn: () => api.get<PlatformFeature[]>("/platform/features") });

  const createModuleMutation = useMutation({
    mutationFn: () => api.post("/platform/modules", { code, name, description }),
    onSuccess: () => {
      setCode("");
      setName("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["platform", "modules"] });
    },
  });

  const featuresByModule = new Map<string, typeof featuresQuery.data>();
  for (const feature of featuresQuery.data ?? []) {
    const list = featuresByModule.get(feature.module_id) ?? [];
    list.push(feature);
    featuresByModule.set(feature.module_id, list);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Modules</h1>
        <p className="mt-1 text-sm text-ink-muted">
          The full module and feature catalog available across all plans. Codes are permanent once created &mdash;
          they&rsquo;re referenced directly by application code, so only name/description can be edited afterward.
        </p>
      </div>

      <Card>
        <CardHeader title="Add a module" />
        {createModuleMutation.isError && (
          <Alert tone="error">{createModuleMutation.error instanceof ApiError ? createModuleMutation.error.message : "Could not create module."}</Alert>
        )}
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            createModuleMutation.mutate();
          }}
        >
          <div className="min-w-[160px] flex-1">
            <Label htmlFor="new-mod-code">Code</Label>
            <Input id="new-mod-code" placeholder="e.g. compliance" value={code} onChange={(e) => setCode(e.target.value)} required />
          </div>
          <div className="min-w-[200px] flex-1">
            <Label htmlFor="new-mod-name">Name</Label>
            <Input id="new-mod-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="min-w-[220px] flex-1">
            <Label htmlFor="new-mod-desc">Description</Label>
            <Input id="new-mod-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <Button type="submit" disabled={createModuleMutation.isPending}>
            Create
          </Button>
        </form>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {modulesQuery.data?.map((module) => (
          <ModuleEditor key={module.id} module={module} features={featuresByModule.get(module.id) ?? []} />
        ))}
      </div>
    </div>
  );
}
