import { defineConfig } from '@playwright/test';

const external = process.env.BROWSER_BASE_URL;
export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: external || 'http://127.0.0.1:5174',
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: external ? undefined : {
    command: 'python tests/browser_server.py',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: false,
    timeout: 60000,
  },
});
