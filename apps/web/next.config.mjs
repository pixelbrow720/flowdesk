/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Compile the workspace TS packages (source, not pre-built) from the monorepo.
  transpilePackages: ["@flowdesk/contracts", "@flowdesk/tokens"],
};

export default nextConfig;
