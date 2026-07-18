import { defineConfig, devices } from '@playwright/test';

const PORTAL_URL = process.env.PORTAL_E2E_URL ?? 'http://127.0.0.1:3100';
const API_URL = process.env.PORTAL_E2E_API_URL ?? 'http://127.0.0.1:3000';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: PORTAL_URL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: process.env.PORTAL_E2E_SKIP_SERVER
    ? undefined
    : {
        command: 'npm run start',
        url: PORTAL_URL,
        reuseExistingServer: true,
        timeout: 120_000,
        env: {
          ...process.env,
          NEXT_PUBLIC_PTT_API_URL: API_URL,
        },
      },
});
