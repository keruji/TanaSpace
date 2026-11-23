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
  projects: [
    { name: 'workspace', testIgnore: '**/development-demo.spec.js' },
    { name: 'development-demo', testMatch: '**/development-demo.spec.js',
      use: { baseURL: process.env.BROWSER_DEV_BASE_URL || 'http://127.0.0.1:5175' } },
  ],
  webServer: external ? undefined : [
    { command: 'python tests/browser_server.py', url: 'http://127.0.0.1:5174',
      env: { BROWSER_TEST_PORT: '5174', BROWSER_TEST_DEV_DEMO: 'false' },
      reuseExistingServer: false, timeout: 60000 },
    { command: 'python tests/browser_server.py', url: 'http://127.0.0.1:5175',
      env: { BROWSER_TEST_PORT: '5175', BROWSER_TEST_DEV_DEMO: 'true' },
      reuseExistingServer: false, timeout: 60000 },
  ],
});
