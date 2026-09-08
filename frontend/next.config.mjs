import { fileURLToPath } from "node:url";
import path from "node:path";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Type errors still fail the build (tsc); we only skip ESLint style nits in CI/Netlify.
  eslint: { ignoreDuringBuilds: true },
  // This directory is the whole app, and saying so is what keeps the console deployable
  // from a Windows machine. Left to inference, Next picks the nearest ancestor holding a
  // lockfile as the workspace root; the Netlify Next.js runtime then treats the app as one
  // package of a monorepo and writes absolute Lambda paths into its server handler with the
  // build machine's path separator — on Windows, backslashes that Node reads as escapes, and
  // the function crashes on first request. With the root pinned here the app is not "inside"
  // anything, and the runtime emits relative paths that carry no separator at all.
  outputFileTracingRoot: path.dirname(fileURLToPath(import.meta.url)),
};

export default nextConfig;
