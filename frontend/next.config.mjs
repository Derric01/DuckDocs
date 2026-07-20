/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  outputFileTracingRoot: process.cwd(),
  turbopack: { root: process.cwd() },
  poweredByHeader: false,
  reactStrictMode: true,
};

export default nextConfig;
