import { test, expect } from '@playwright/test';

const STAFF_EMAIL = process.env.OPS_E2E_STAFF_EMAIL ?? 'staff@demo.local';
const STAFF_PASSWORD = process.env.OPS_E2E_STAFF_PASSWORD ?? 'demo123';
const PILOT_CLIENT_ID = process.env.OPS_ONBOARD_CLIENT_ID ?? '';

async function loginAsStaff(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(STAFF_EMAIL);
  await page.getByLabel(/mật khẩu|password/i).fill(STAFF_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

test.describe('Prod-S5 onboard wizard', () => {
  test('onboard tab shows wizard stepper', async ({ page }) => {
    test.skip(!PILOT_CLIENT_ID, 'OPS_ONBOARD_CLIENT_ID not set');
    await loginAsStaff(page);
    await page.goto(`/agency/clients/${PILOT_CLIENT_ID}?tab=onboard`);
    await expect(page.getByText(/CRM & Lifecycle|Kết nối channel/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('button', { name: /Bước tiếp/i })).toBeVisible();
  });
});
