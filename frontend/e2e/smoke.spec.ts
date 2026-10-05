/**
 * B6 冒烟链路：书架导入 → 阅读器；万能抓取 → 任务中心 → 资源库。
 * 后端由 playwright.config.ts 的 webServer 启动（127.0.0.1:8687，
 * 托管 frontend/dist 与独立数据目录 backend/.e2e-data）。
 */
import { test, expect } from '@playwright/test'

const NOVEL_TXT = `冒烟测试之书
作者：墨读

第一章 开端

清晨的雾气还未散去，少年已经背起行囊，踏上了通往山外的旅途。

第二章 归途

黄昏时分，他终于回到了久别的故乡，炊烟正起。

`
const SAMPLE_URL = 'https://example.com/'

test('书架导入 → 阅读器打开正文', async ({ page }) => {
  await page.goto('/shelf')
  await expect(page.getByRole('heading', { name: '书架' })).toBeVisible({ timeout: 30_000 })

  await page.setInputFiles('input[type="file"]', {
    name: 'smoke-novel.txt', mimeType: 'text/plain', buffer: Buffer.from(NOVEL_TXT, 'utf-8'),
  })
  await expect(page.getByText('冒烟测试之书').first()).toBeVisible({ timeout: 60_000 })

  await page.getByText('冒烟测试之书').first().click()
  await expect(page).toHaveURL(/\/reader\//)
  await expect(page.getByText('清晨的雾气还未散去').first()).toBeVisible({ timeout: 30_000 })
})

test('万能抓取 → 任务中心完成 → 资源库可见', async ({ page }) => {
  await page.goto('/grab')
  await page.getByPlaceholder('https://example.com/novel-or-image-or-video…').fill(SAMPLE_URL)
  // 类型保持「自动识别」：example.com 应被判定为网页，走内置网页归档兜底
  await page.getByRole('button', { name: /一键抓取/ }).click()

  await page.goto('/tasks')
  const card = page.locator('div', { has: page.getByText(SAMPLE_URL) }).last()
  await expect(
    card.getByText('已完成').first(),
  ).toBeVisible({ timeout: 90_000 })

  await page.goto('/library')
  await page.getByRole('button', { name: '网页', exact: true }).click()
  // 归档卡片标题取自网页 <title>（Example Domain）；卡片可点进详情页
  await page.getByText('Example Domain').first().click()
  await expect(page).toHaveURL(/\/library\/media\//)
})
