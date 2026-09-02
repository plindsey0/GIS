import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev and production builds must never rewrite one another's chunk manifests.
  distDir: process.env.NEXT_DIST_DIR ?? ".next-build",
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{source: "/(.*)", headers: [
      {key: "X-Content-Type-Options", value: "nosniff"},
      {key: "X-Frame-Options", value: "DENY"},
      {key: "Referrer-Policy", value: "no-referrer"}
    ]}];
  }
};

export default nextConfig;
