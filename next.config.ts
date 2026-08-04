import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Statically exported so it can be uploaded as plain HTML/CSS/JS to
  // shared hosting (e.g. IONOS webspace over FTP) that doesn't run a
  // Node.js server. See README.md "Deploying to static/shared hosting".
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  turbopack: {
    rules: {
      "*.glsl": {
        loaders: ["raw-loader"],
        as: "*.js",
      },
    },
  },
};

export default nextConfig;
