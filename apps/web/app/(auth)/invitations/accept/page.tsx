"use client";

import { Banner, Button, Card } from "@gridkeep/ui";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { useSession } from "@/lib/session";

function AcceptInvitationContent() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const { data: session, isLoading } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [isAccepting, setIsAccepting] = useState(false);

  const handleAccept = async () => {
    setError(null);
    setIsAccepting(true);
    try {
      await api.post("/invitations/accept", { token });
      await queryClient.invalidateQueries({ queryKey: ["session"] });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept this invitation.");
    } finally {
      setIsAccepting(false);
    }
  };

  if (!token) {
    return <Banner tone="error">This invitation link is missing its token.</Banner>;
  }

  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading...</p>;
  }

  if (!session) {
    return (
      <div className="flex flex-col gap-4">
        <Banner tone="info">Sign in or create an account with the email this invitation was sent to, then come back to this link to accept it.</Banner>
        <div className="flex gap-3">
          <Link href={`/login?next=/invitations/accept?token=${token}`} className="text-sm font-medium text-brand-600 hover:underline">
            Sign in
          </Link>
          <Link href={`/register?next=/invitations/accept?token=${token}`} className="text-sm font-medium text-brand-600 hover:underline">
            Register
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-600 dark:text-slate-300">
        You&apos;re signed in as <strong>{session.user.email}</strong>. Accept this invitation to join the workspace.
      </p>
      {error && <Banner tone="error">{error}</Banner>}
      <Button onClick={handleAccept} isLoading={isAccepting} className="w-full">
        Accept invitation
      </Button>
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <Card className="w-full max-w-sm">
        <h1 className="mb-6 text-xl font-semibold">Accept invitation</h1>
        <Suspense fallback={<p className="text-sm text-slate-500">Loading...</p>}>
          <AcceptInvitationContent />
        </Suspense>
      </Card>
    </main>
  );
}
