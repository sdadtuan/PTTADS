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

test.describe('CSKH board Prod-S4', () => {
  test('cskh-board loads SLA summary', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/crm/cskh-board');
    await expect(page.getByRole('heading', { name: /Bảng CSKH/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Breach|Warning|OK/i)).toBeVisible();
  });
});
