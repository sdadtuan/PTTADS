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

test.describe('Ops Zalo prod cutover smoke (Prod-S3)', () => {
  test('zalo-ads hub has CPA fields and no stub banner when prod flags', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/zalo/zalo-ads');
    await expect(page.getByRole('heading', { name: /Zalo Ads Hub/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('columnheader', { name: /CPA|Won/i })).toBeVisible();
    await expect(page.getByText(/stub mode/i)).toHaveCount(0);
  });

  test('zalo leads form sync page loads', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/zalo/leads');
    await expect(page.getByRole('heading', { name: /Zalo leads|Form sync/i })).toBeVisible({
      timeout: 15_000,
    });
  });
});
