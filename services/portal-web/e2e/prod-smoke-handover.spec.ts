import { test, expect } from '@playwright/test';

/** PROD-H-E2E — handover/06 §2.3 F2 + F7 (portal-web). */
const APPROVER_EMAIL = process.env.PORTAL_E2E_APPROVER_EMAIL ?? 'approver@demo.local';
const APPROVER_PASSWORD = process.env.PORTAL_E2E_APPROVER_PASSWORD ?? 'demo123';

async function loginAsApprover(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(APPROVER_EMAIL);
  await page.getByLabel(/mật khẩu|password/i).fill(APPROVER_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
}

test.describe('PROD-H handover smoke F2/F7 (portal-web)', () => {
  test('F2 — portal login + dashboard performance', async ({ page }) => {
    await loginAsApprover(page);
    await expect(page.getByText(/Performance Meta \+ Google \+ Zalo/i)).toBeVisible({
      timeout: 15_000,
    });
  });

  test('F7 — approver creative inbox reachable', async ({ page }) => {
    await loginAsApprover(page);
    await page.getByRole('link', { name: /creative inbox/i }).click();
    await expect(page).toHaveURL(/\/creatives/);
    await expect(page.getByRole('heading', { name: /creative inbox/i })).toBeVisible({
      timeout: 15_000,
    });
  });
});
