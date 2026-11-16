import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig(base, {
  testDir: './e2e-identity',
  workers: 1,
  timeout: 45000,
  use: { ...base.use, trace: 'off' },
});
