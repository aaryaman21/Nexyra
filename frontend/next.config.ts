import type { NextConfig } from "next";

const config: NextConfig = {
  // Next's dev HMR endpoint validates the browser Origin separately from
  // backend rewrites; allow both loopback names used by local Nexyra URLs.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [{ source: "/api/agri/:path*", destination: `${process.env.NEXYRA_BACKEND_URL || "http://127.0.0.1:8000"}/api/agri/:path*` }];
  },
};

export default config;
