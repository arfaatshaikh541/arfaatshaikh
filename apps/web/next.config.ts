import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output traces only the dependencies each page actually
  // needs into .next/standalone, so the production image can ship a
  // node_modules-free runtime stage instead of the full workspace install.
  output: "standalone",
};

export default nextConfig;
