/**
 * The web app calls only /api/v1/*. In development (and on any single host) Next proxies that
 * to CURO's FastAPI backend at API_ORIGIN. On Vercel later, the API runs as its own service on
 * the same domain under /api (docs/DEPLOY_VERCEL.md); this rewrite is then unused.
 */
const API_ORIGIN = process.env.API_ORIGIN || 'http://127.0.0.1:8000';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${API_ORIGIN}/v1/:path*` }];
  },
};

export default nextConfig;
