/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a minimal standalone server for a small production Docker image.
  output: "standalone",
};

export default nextConfig;
