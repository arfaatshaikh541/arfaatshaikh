"use client";

import dynamic from "next/dynamic";
import { SphereFallback } from "./SphereFallback";

export const SphereCanvasLazy = dynamic(
  () => import("./SphereScene").then((mod) => mod.SphereScene),
  {
    ssr: false,
    loading: () => <SphereFallback />,
  }
);
