/**
 * The web app calls only /api/v1/*. In development (and on any single host) Next proxies that
 * to CURO's FastAPI backend at API_ORIGIN. On Vercel later, the API runs as its own service on
 * the same domain under /api (docs/DEPLOY_VERCEL.md); this rewrite is then unused.
 */
const API_ORIGIN = process.env.API_ORIGIN || 'http://127.0.0.1:8000';

// Demo mode (D211): deployed on Vercel with no backend to call, play back the recorded demo.
// Set API_ORIGIN (or NEXT_PUBLIC_DEMO_MODE=false) once the API is hosted.
const DEMO_MODE =
  process.env.NEXT_PUBLIC_DEMO_MODE ??
  ((process.env.VERCEL && !process.env.API_ORIGIN) || process.env.npm_lifecycle_event === 'dev:demo'
    ? 'true'
    : 'false');

const DIST = process.env.npm_lifecycle_event === 'dev:demo' ? '.next-demo' : '.next';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep Turbopack anchored to the web app in the repository's multi-app layout.
  // This prevents dependency resolution from escaping to the Expo app's lockfile.
  turbopack: {
    root: process.cwd(),
  },
  distDir: DIST,
  reactStrictMode: true,
  env: { NEXT_PUBLIC_DEMO_MODE: DEMO_MODE },
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${API_ORIGIN}/v1/:path*` }];
  },
};

export default nextConfig;
