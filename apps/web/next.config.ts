import type { NextConfig } from "next";

const api = process.env.API_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  devIndicators: false,
  experimental: { proxyTimeout: 600000 },
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async redirects() {
    // The browser must receive the OAuth cookie from the callback host.
    return [{ source: "/api/auth/start", destination: `${api}/api/auth/start`, permanent: false }];
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/auth/:path*", destination: `${api}/auth/:path*` },
    ];
  },
};

export default nextConfig;
