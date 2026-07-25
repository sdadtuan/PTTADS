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

test.describe('Portal notifications E2E (Prod-S1)', () => {
  test('submit creative → client sees notification within inbox', async ({ page, request }) => {
    const title = `E2E Notify ${Date.now()}`;
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
        description: 'Prod-S1 notification emit test',
        external_campaign_id: 'camp_e2e_notify',
        version: 1,
        submitted_by: 'e2e@pttads.vn',
      },
    });
    expect(submit.ok(), `seed creative failed: ${submit.status()}`).toBeTruthy();

    await loginAsApprover(page);
    await page.getByRole('link', { name: /thông báo/i }).click();
    await expect(page).toHaveURL(/\/notifications/);
    await expect(page.getByText(title)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/creative chờ duyệt/i)).toBeVisible();
  });

  test('notifications page mark read', async ({ page }) => {
    await loginAsApprover(page);
    await page.getByRole('link', { name: /thông báo/i }).click();
    await expect(page.getByRole('heading', { name: /trung tâm thông báo/i })).toBeVisible();
    const markRead = page.getByRole('button', { name: /^đã đọc$/i }).first();
    if (await markRead.isVisible().catch(() => false)) {
      await markRead.click();
    }
  });

  test('dashboard pending widget visible', async ({ page }) => {
    await loginAsApprover(page);
    await expect(page.getByText(/thông báo & duyệt/i)).toBeVisible({ timeout: 15_000 });
  });
});
