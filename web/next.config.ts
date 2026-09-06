import type { NextConfig } from "next";

/*
  Two settings, both deliberate.

  turbopack.root pins the workspace to this directory. Without it the bundler
  walks up past the repository looking for a lockfile and warns about one it
  found in a home directory.

  No image loader, no font loader, no analytics, no telemetry-bearing plugin:
  the demo runs with the network physically off, and this application talks to
  exactly one origin, the local FastAPI process.
*/

const nextConfig: NextConfig = {
  turbopack: {
    root: import.meta.dirname,
  },
};

export default nextConfig;
