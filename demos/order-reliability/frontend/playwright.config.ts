import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';

const python = resolve(
  '..',
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 } },
  reporter: [['list'], ['json', { outputFile: 'test-results/browser.json' }]],
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`,
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/health',
      env: { LAB_DATA_DIR: resolve('..', '.data', 'browser-tests') },
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
    },
  ],
});
