import path from "path";
import type { NextConfig } from "next";

const isLocalTestServer = process.env.LOCAL_TEST_SERVER === "1";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  output: "standalone", // For Docker deployment
  turbopack: {
    root: path.resolve(__dirname),
  },
  typescript: {
    // Next spawns a separate checker process on Windows; keep that off only for local sandbox runs.
    ignoreBuildErrors: isLocalTestServer,
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
};

export default nextConfig;
