import { test, expect } from '@playwright/test';

/**
 * PROD-H-E2E — handover/06 §2.3 F1, F3–F6 smoke (ops-web + API).
 * F2/F7 (portal login + approver) live in portal-web/e2e/prod-smoke-handover.spec.ts.
 */
const STAFF_EMAIL = process.env.OPS_E2E_STAFF_EMAIL ?? 'staff@demo.local';
const STAFF_PASSWORD = process.env.OPS_E2E_STAFF_PASSWORD ?? 'demo123';
const API_URL = (process.env.OPS_E2E_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');

async function loginAsStaff(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(STAFF_EMAIL);
  await page.getByLabel(/mật khẩu|password/i).fill(STAFF_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

test.describe('PROD-H handover smoke F1/F3–F6 (ops-web)', () => {
  test('F1 — staff login + CRM leads list', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/crm/leads');
    await expect(page.getByRole('heading', { name: /Leads|CRM leads/i })).toBeVisible({
      timeout: 15_000,
    });
  });

  test('F3 — Meta hub loads T-1 attribution', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/meta/facebook-ads');
    await expect(page.getByRole('tab', { name: /^Clients$/i })).toBeVisible({ timeout: 15_000 });
  });

  test('F4 — SEO hub load', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/seo/hub');
    await expect(page.getByRole('heading', { name: 'SEO/AEO Hub' })).toBeVisible({
      timeout: 15_000,
    });
  });

  test('F5 — Email hub load', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/email/hub');
    await expect(page.getByText(/EM-0 — Email Ops hub|E-01/i)).toBeVisible({ timeout: 15_000 });
  });

  test('F6 — lead ingest webhook health (Nest API)', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/health`);
    expect(res.ok()).toBeTruthy();
    const health = await request.get(`${API_URL}/api/v1/health`);
    expect(health.ok()).toBeTruthy();
  });

  test('Prod-S4 — CSKH SLA board reachable from CRM', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/crm/cskh-board');
    await expect(page.getByRole('heading', { name: /Bảng CSKH/i })).toBeVisible({
      timeout: 15_000,
    });
  });
});
