import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output — the Docker build (frontend/Dockerfile) copies just
  // .next/standalone + .next/static instead of the whole node_modules tree.
  // Not used by the actual deployment target (Cloudflare Pages, via its own
  // Next.js adapter), but keeps a container-based fallback/local-parity
  // option available without a separate build config.
  output: "standalone",
};

export default nextConfig;
