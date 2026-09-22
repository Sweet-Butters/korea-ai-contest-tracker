import type { NextConfig } from "next";

// BASE_PATH is "/<repo>" on GitHub Pages and empty for local dev.
const basePath = process.env.BASE_PATH ?? "";

const config: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
  transpilePackages: ["@radar/shared"],
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default config;
