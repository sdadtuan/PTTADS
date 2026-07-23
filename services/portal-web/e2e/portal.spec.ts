import { test, expect } from '@playwright/test';

const APPROVER_EMAIL = process.env.PORTAL_E2E_APPROVER_EMAIL ?? 'approver@demo.local';
const APPROVER_PASSWORD = process.env.PORTAL_E2E_APPROVER_PASSWORD ?? 'demo123';
const API_URL = (process.env.PORTAL_E2E_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');
const CLIENT_ID = process.env.PORTAL_E2E_CLIENT_ID ?? '550e8400-e29b-41d4-a716-446655440000';

async function loginAsApprover(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(APPROVER_EMAIL);
  await page.getByLabel(/mật khẩu|password/i).fill(APPROVER_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

test.describe('Client portal E2E', () => {
  test('login → dashboard performance', async ({ page }) => {
    await loginAsApprover(page);
    await expect(page.getByText(/Performance Meta \+ Google/i)).toBeVisible({ timeout: 15_000 });
  });

  test('navigate to creative inbox', async ({ page }) => {
    await loginAsApprover(page);
    await page.getByRole('link', { name: /creative inbox/i }).click();
    await expect(page).toHaveURL(/\/creatives/);
    await expect(page.getByRole('heading', { name: /creative inbox/i })).toBeVisible();
  });

  test('navigate to Meta performance tab', async ({ page }) => {
    await loginAsApprover(page);
    await page.getByRole('link', { name: /meta \(facebook\)/i }).click();
    await expect(page).toHaveURL(/\/meta/);
    await expect(page.getByText(/Meta Performance \(Facebook \/ Instagram\)/i)).toBeVisible({
      timeout: 15_000,
    });
  });

  test('approver duyệt creative pending (Temporal seed)', async ({ page, request }) => {
    const title = process.env.PORTAL_E2E_CREATIVE_TITLE ?? `E2E Creative ${Date.now()}`;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const internalKey = process.env.PORTAL_E2E_INTERNAL_KEY ?? process.env.PTT_CRM_INTERNAL_KEY;
    if (internalKey) {
      headers['X-PTT-Internal-Key'] = internalKey;
    }

    const submit = await request.post(`${API_URL}/api/v1/creatives`, {
      headers,
      data: {
        client_id: CLIENT_ID,
        title,
        description: 'Playwright approve — Temporal workflow',
        external_campaign_id: 'camp_e2e_playwright',
        version: 1,
        submitted_by: 'e2e@pttads.vn',
      },
    });
    expect(submit.ok(), `seed creative failed: ${submit.status()}`).toBeTruthy();

    await loginAsApprover(page);
    await page.getByRole('link', { name: /creative inbox/i }).click();
    await expect(page.getByText(title)).toBeVisible({ timeout: 15_000 });

    await page.getByRole('button', { name: /^Duyệt$/i }).first().click();
    await page.getByRole('button', { name: /xác nhận duyệt/i }).click();
    await expect(page.getByText(title)).not.toBeVisible({ timeout: 15_000 });
  });

  test('creative history tab loads', async ({ page }) => {
    await loginAsApprover(page);
    await page.getByRole('link', { name: /creative inbox/i }).click();
    await page.getByRole('button', { name: /lịch sử 30 ngày/i }).click();
    await expect(page.getByRole('button', { name: /lịch sử 30 ngày/i })).toBeVisible();
  });

  test('settings page loads for approver', async ({ page }) => {
    await loginAsApprover(page);
    await page.getByRole('link', { name: /cài đặt/i }).click();
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.getByText(/Branding/i)).toBeVisible();
  });
});
