/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@leadflow/ui", "@leadflow/shared-types"],
  reactStrictMode: true,
  output: "standalone",
};

export default nextConfig;
