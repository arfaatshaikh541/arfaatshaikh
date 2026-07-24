"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function HomePage() {
  const { user, loading } = useAuth();

  return (
    <main id="main-content" className="flex flex-1 flex-col items-center justify-center gap-6 p-16 text-center">
      <h1 className="text-4xl font-semibold tracking-tight">GRIDKEEP</h1>
      <p className="max-w-xl text-lg text-zinc-600 dark:text-zinc-400">
        Sovereign AI Network Exchange &mdash; federated telecom infrastructure for sovereign
        enterprise and government AI workloads.
      </p>
      {!loading && (
        <div className="flex gap-4 flex-wrap">
          {user ? (
            <Link
              className="rounded-full bg-zinc-900 px-6 py-3 font-medium text-white dark:bg-white dark:text-zinc-900"
              href="/dashboard"
            >
              Go to dashboard
            </Link>
          ) : (
            <>
              <Link
                className="rounded-full bg-zinc-900 px-6 py-3 font-medium text-white dark:bg-white dark:text-zinc-900"
                href="/login"
              >
                Log in
              </Link>
              <Link
                className="rounded-full border border-zinc-300 px-6 py-3 font-medium dark:border-zinc-700"
                href="/register"
              >
                Register
              </Link>
            </>
          )}
        </div>
      )}
    </main>
  );
}
