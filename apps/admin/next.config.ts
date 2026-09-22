import type { NextConfig } from "next";

// Served under <site>/admin, next to the main web app.
const root = process.env.BASE_PATH ?? "";

const config: NextConfig = {
  output: "export",
  basePath: `${root}/admin`,
  trailingSlash: true,
  images: { unoptimized: true },
  transpilePackages: ["@radar/shared"],
  env: { NEXT_PUBLIC_SITE_ROOT: root },
};

export default config;
