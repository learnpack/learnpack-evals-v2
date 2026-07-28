/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Type errors still fail the build (tsc); we only skip ESLint style nits in CI/Netlify.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
