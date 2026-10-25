import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

// Unit tests for components (v2.2: the persona avatar, Home's order, the Studio persona row and
// its popover). They run in jsdom and never call the API.
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
