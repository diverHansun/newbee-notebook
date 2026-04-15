import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    serverActions: {
      bodySizeLimit: "500mb",
    },
    // Raise the default 10 MB body-size cap that Next.js applies
    // when proxying requests through middleware / rewrites.
    middlewareClientMaxBodySize: 500 * 1024 * 1024, // 500 MB
  } as NextConfig["experimental"],
  async rewrites() {
    const apiHost = (process.env.INTERNAL_API_URL || "http://127.0.0.1:8000").trim();
    return {
      // Keep the catch-all backend proxy as a fallback so local app/api route
      // handlers (for streaming and long /chat requests) win first.
      fallback: [
        {
          source: "/api/v1/:path*",
          destination: `${apiHost}/api/v1/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
