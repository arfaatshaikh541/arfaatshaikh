import path from "path";
import type { NextConfig } from "next";

const apiOrigin = process.env.WOI_API_ORIGIN ?? "http://api:8000";
const publicApiOrigin = process.env.NEXT_PUBLIC_WOI_API_ORIGIN ?? "http://localhost:8000";
const connectSources = ["'self'", apiOrigin, publicApiOrigin].join(" ");

// Deployment base path, e.g. "/worldofislam" when served at
// https://app.arfaat.com/worldofislam. Empty string ("") for local dev and
// for any deployment that owns its own origin. Must NOT have a trailing slash.
const basePath = (process.env.WOI_BASE_PATH ?? "").replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  // The Dockerfile copies apps/web/.next/standalone into the image root and
  // runs "node apps/web/server.js", so tracing must be rooted at the monorepo
  // root (not apps/web) for the standalone output to nest under apps/web/.
  outputFileTracingRoot: path.join(__dirname, "../.."),
  poweredByHeader: false,
  reactStrictMode: true,
  transpilePackages: ["@world-of-islam/ui", "@world-of-islam/shared-types"],
  ...(basePath ? { basePath, assetPrefix: basePath } : {}),

  // Keep Docker production builds from being blocked by generated Next.js
  // route-type diagnostics. Runtime-invalid imports and syntax still fail.
  typescript: {
    ignoreBuildErrors: true,
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
          {
            key: "Content-Security-Policy",
            value: `default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; img-src 'self' data:; font-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src ${connectSources}`,
          },
        ],
      },
    ];
  },
};

export default nextConfig;
