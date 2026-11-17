import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.pw.ts',
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:3000',
    channel: process.env.PW_CHANNEL || 'chromium',
  },
});
