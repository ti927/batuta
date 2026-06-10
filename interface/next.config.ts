import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Bundle mínimo e autossuficiente para rodar em container (Railway/Docker).
  output: "standalone",
};

export default nextConfig;
