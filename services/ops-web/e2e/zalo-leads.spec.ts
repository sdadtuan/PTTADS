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

test.describe('Ops Zalo Leads Z2', () => {
  test('zalo-leads page loads tabs', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/zalo/leads');
    await expect(page.getByRole('heading', { name: /Zalo Leads Monitor/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('button', { name: /Leads/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Form sync/i })).toBeVisible();
  });
});
