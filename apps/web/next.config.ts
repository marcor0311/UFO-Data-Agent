import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  experimental: { proxyTimeout: 600000 },
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    const api = process.env.API_URL || "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/auth/:path*", destination: `${api}/auth/:path*` },
    ];
  },
};

export default nextConfig;
