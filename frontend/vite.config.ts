import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Dev server runs on port 3000 and proxies API calls to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    css: false,
  },
});
