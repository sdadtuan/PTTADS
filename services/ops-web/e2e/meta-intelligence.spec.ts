import { test, expect } from '@playwright/test';

const STAFF_EMAIL = process.env.OPS_E2E_STAFF_EMAIL ?? 'staff@demo.local';
const STAFF_PASSWORD = process.env.OPS_E2E_STAFF_PASSWORD ?? 'demo123';

async function loginAsStaff(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(STAFF_EMAIL);
  await page.getByLabel(/mật khẩu|password/i).fill(STAFF_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).toHaveURL(/\//);
}

test.describe('Ops Meta intelligence B10 E2E', () => {
  test('intelligence page ROAS KPI + chart + anomalies + recommendations', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/meta/intelligence');
    await expect(page.getByRole('heading', { name: /Meta Intelligence/i })).toBeVisible({
      timeout: 15_000,
    });

    await expect(page.getByRole('heading', { name: /ROAS KPI/i })).toBeVisible();
    await expect(page.locator('.meta-intelligence-roas-chart')).toBeVisible();
    await expect(page.getByRole('heading', { name: /^Anomalies$/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Budget recommendations/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Insights daily/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Stat anomalies/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Forecast/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Multi-pixel/i })).toBeVisible();
  });

  test('intelligence filters and refresh button', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/meta/intelligence');
    await expect(page.getByRole('button', { name: /Làm mới/i })).toBeVisible({ timeout: 15_000 });
    await page.getByRole('button', { name: /Làm mới/i }).click();
    await expect(page.getByRole('heading', { name: /Meta Intelligence/i })).toBeVisible();
  });
});
