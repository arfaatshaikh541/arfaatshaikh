"use client";

import { Alert, Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { TrustPassportSettingsRead } from "@/lib/types";

export default function TrustPassportSettingsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("trust_passport.manage");
  const queryClient = useQueryClient();

  const [headline, setHeadline] = useState("");
  const [description, setDescription] = useState("");
  const [showComplianceFrameworks, setShowComplianceFrameworks] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [copyNotice, setCopyNotice] = useState<string | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["trust-passport", "settings"],
    queryFn: () => apiClient.get<TrustPassportSettingsRead>("/api/trust-passport/settings"),
    enabled: canManage,
  });

  useEffect(() => {
    if (!settingsQuery.data) return;
    setHeadline(settingsQuery.data.headline);
    setDescription(settingsQuery.data.description);
    setShowComplianceFrameworks(settingsQuery.data.show_compliance_frameworks);
  }, [settingsQuery.data]);

  if (!canManage) {
    return <Alert tone="info">You don&apos;t have permission to manage the trust passport.</Alert>;
  }

  const settings = settingsQuery.data;

  const save = async (isPublished: boolean) => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.patch("/api/trust-passport/settings", {
        is_published: isPublished,
        headline,
        description,
        show_compliance_frameworks: showComplianceFrameworks,
      });
      queryClient.invalidateQueries({ queryKey: ["trust-passport", "settings"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const regenerateSlug = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post("/api/trust-passport/settings/regenerate-slug");
      queryClient.invalidateQueries({ queryKey: ["trust-passport", "settings"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const publicUrl = settings?.public_slug
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/trust/${settings.public_slug}`
    : null;

  const copyUrl = () => {
    if (!publicUrl) return;
    navigator.clipboard.writeText(publicUrl);
    setCopyNotice("Copied!");
    setTimeout(() => setCopyNotice(null), 2000);
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Trust Passport</h1>
        <p className="text-sm text-ink-500">
          A public, shareable page summarizing your security program — safe to send to a prospect or
          customer without giving them access to GRIDKEEP itself.
        </p>
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <Card>
        <CardHeader
          title="Status"
          description={
            settings?.is_published
              ? "Your trust passport is live and publicly reachable at the link below."
              : "Your trust passport is not published yet — the page below is only a preview."
          }
        />
        <div className="flex items-center gap-3">
          <StatusBadge
            label={settings?.is_published ? "Published" : "Draft"}
            tone={settings?.is_published ? "positive" : "neutral"}
          />
          {publicUrl ? (
            <>
              <code className="rounded bg-surface-800 px-2 py-1 text-sm text-ink-700">{publicUrl}</code>
              <Button size="sm" variant="ghost" onClick={copyUrl}>
                {copyNotice ?? "Copy link"}
              </Button>
              <Button size="sm" variant="ghost" isLoading={isBusy} onClick={regenerateSlug}>
                Regenerate link
              </Button>
            </>
          ) : (
            <p className="text-sm text-ink-500">Publish to generate a public link.</p>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Content" description="What visitors to your public page will see." />
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="headline" className="text-sm font-medium text-ink-700">
              Headline
            </label>
            <input
              id="headline"
              type="text"
              placeholder="Acme Corp takes security seriously"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="description" className="text-sm font-medium text-ink-700">
              Description
            </label>
            <textarea
              id="description"
              rows={4}
              placeholder="A short summary of your security program for prospects and customers."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="rounded border border-surface-border bg-surface-800 px-3 py-2 text-sm text-ink-900"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={showComplianceFrameworks}
              onChange={(e) => setShowComplianceFrameworks(e.target.checked)}
            />
            Show compliance framework status (as a coarse label, never the raw score)
          </label>
          <div className="flex gap-2">
            <Button isLoading={isBusy} onClick={() => save(true)}>
              {settings?.is_published ? "Save changes" : "Publish"}
            </Button>
            {settings?.is_published ? (
              <Button variant="secondary" isLoading={isBusy} onClick={() => save(false)}>
                Unpublish
              </Button>
            ) : null}
          </div>
        </div>
      </Card>
    </div>
  );
}
