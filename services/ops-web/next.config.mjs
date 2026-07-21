/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  async redirects() {
    return [
      { source: '/crm/agency', destination: '/agency', permanent: false },
      { source: '/crm/agency/:path*', destination: '/agency/:path*', permanent: false },
    ];
  },
};

export default nextConfig;
