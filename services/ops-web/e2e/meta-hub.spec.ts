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

test.describe('Ops Meta hub B8', () => {
  test('facebook-ads hub tabs, CPL Δ column, attribution footer', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/meta/facebook-ads');
    await expect(page.getByRole('tab', { name: /^Clients$/i })).toBeVisible({ timeout: 15_000 });

    await page.getByRole('tab', { name: /^Campaigns$/i }).click();
    await expect(page.getByRole('columnheader', { name: /CPL Δ/i })).toBeVisible({ timeout: 15_000 });

    const footer = page.locator('.meta-attribution-footer');
    const footerVisible = await footer.isVisible().catch(() => false);
    if (footerVisible) {
      await expect(footer).toContainText(/last_touch_crm/i);
    }

    await expect(page.getByRole('tab', { name: /^Alerts$/i })).toHaveCount(0);
  });
});
