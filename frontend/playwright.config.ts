import { defineConfig, devices } from '@playwright/test'

// B6 冒烟：后端同时托管前端构建产物（frontend/dist），一个 webServer 即可。
// 前置：pnpm run build（CI 会先执行）；数据目录隔离在 backend/.e2e-data。
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:8687',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8687',
    cwd: '../backend',
    url: 'http://127.0.0.1:8687/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { MOREAD_DATA_DIR: './.e2e-data' },
  },
})
