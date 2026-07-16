"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function PlatformIndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/platform/tenants");
  }, [router]);

  return null;
}
