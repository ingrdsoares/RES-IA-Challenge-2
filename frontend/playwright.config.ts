import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.pw.ts',
  workers: 1,
  webServer: process.env.PW_PREVIEW === '1' ? {
    command: 'npm run preview -- --host 127.0.0.1 --port 3000 --strictPort',
    url: 'http://localhost:3000',
  } : undefined,
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:3000',
    channel: process.env.PW_CHANNEL || 'chromium',
  },
});
