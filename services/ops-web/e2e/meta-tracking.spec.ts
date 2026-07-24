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

test.describe('Ops Meta tracking B9 E2E-M4', () => {
  test('tracking page KPI grid + test pixel inline OK', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/meta/tracking');
    await expect(page.getByRole('heading', { name: /Meta Tracking/i })).toBeVisible({
      timeout: 15_000,
    });

    await expect(page.locator('.meta-tracking-kpi-grid')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/^Sent$/i).first()).toBeVisible();

    const testBtn = page.getByRole('button', { name: /Test pixel/i }).first();
    const hasTest = await testBtn.isVisible().catch(() => false);
    if (hasTest) {
      await testBtn.click();
      await expect(page.locator('.meta-tracking-test-ok, .meta-tracking-test-fail').first()).toBeVisible({
        timeout: 20_000,
      });
    }

    await expect(page.getByRole('heading', { name: /Conversion rules/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /CAPI event log/i })).toBeVisible();
  });

  test('conversion rules table loads for viewer', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/meta/tracking');
    await expect(page.getByRole('columnheader', { name: /Event/i })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole('columnheader', { name: /^Status$/i })).toBeVisible();
  });
});
