import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NODE_ENV === "production" ? ".next-build" : ".next",
  allowedDevOrigins: ["127.0.0.1"]
};

export default nextConfig;
