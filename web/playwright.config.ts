import { defineConfig, devices } from '@playwright/test';
import { resolve } from 'node:path';

const python = '"' + resolve('..', '.venv', process.platform === 'win32'
  ? 'Scripts/python.exe' : 'bin/python').replaceAll('\\', '/') + '"';
const externalBaseURL = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  use: {
    baseURL: externalBaseURL || 'http://127.0.0.1:15173',
    ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}),
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-web', use: { ...devices['Pixel 7'], defaultBrowserType: 'chromium' } },
  ],
  webServer: externalBaseURL ? undefined : [
    {
      command: `${python} -m alembic -c ../backend/alembic.ini upgrade head && ${python} -m uvicorn app.main:app --host 127.0.0.1 --port 18000 --no-access-log`,
      env: { DATABASE_URL: 'sqlite:///./e2e.db', CORS_ORIGINS: 'http://127.0.0.1:15173' },
      url: 'http://127.0.0.1:18000/api/v1/health',
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 15173',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:18000' },
      url: 'http://127.0.0.1:15173',
      reuseExistingServer: false,
    },
  ],
});
