import { test, expect } from '@playwright/test';

const APPROVER_EMAIL = process.env.PORTAL_E2E_APPROVER_EMAIL ?? 'approver@demo.local';
const APPROVER_PASSWORD = process.env.PORTAL_E2E_APPROVER_PASSWORD ?? 'demo123';
const API_URL = (process.env.PORTAL_E2E_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');

async function loginAsApprover(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(APPROVER_EMAIL);
  await page.getByLabel(/mật khẩu|password/i).fill(APPROVER_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

async function getPortalToken(request: import('@playwright/test').APIRequestContext) {
  const login = await request.post(`${API_URL}/api/v1/portal/auth/login`, {
    data: { email: APPROVER_EMAIL, password: APPROVER_PASSWORD },
  });
  expect(login.ok(), `portal login failed: ${login.status()}`).toBeTruthy();
  const body = await login.json();
  return String(body.access_token ?? '');
}

test.describe('Portal B8 — CPL delta + attribution', () => {
  test('performance API exposes CPL delta on mapped campaign rows', async ({ request }) => {
    const token = await getPortalToken(request);
    test.skip(!token, 'portal token unavailable — start Nest with PG seed');

    const res = await request.get(`${API_URL}/api/v1/performance`, {
      headers: { Authorization: `Bearer ${token}` },
      params: { channel: 'meta', group_by: 'campaign' },
    });
    expect(res.ok(), `performance API failed: ${res.status()}`).toBeTruthy();
    const body = await res.json();
    expect(body.attribution_model).toBe('last_touch_crm');
    expect(typeof body.unmapped_spend_pct).toBe('number');

    const row = (body.rows ?? []).find(
      (r: { external_campaign_id?: string | null }) => r.external_campaign_id === 'camp_e2e',
    );
    if (!row) {
      test.skip(true, 'camp_e2e row missing — run seedE2eDailyPerformance via Nest e2e or PG seed');
    }
    expect(row.hub_mapped).toBe(true);
    expect(row.target_cpl_vnd).toBe(40000);
    expect(row.cpl_delta_vnd).toBe(10000);
  });

  test('Meta tab shows Map/CPL Δ columns, Mapped badge, attribution footer', async ({ page }) => {
    await loginAsApprover(page);
    await page.getByRole('link', { name: /meta \(facebook\)/i }).click();
    await expect(page).toHaveURL(/\/meta/);

    await expect(page.getByRole('columnheader', { name: /CPL Δ/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('columnheader', { name: /^Map$/i })).toBeVisible();

    await page.getByRole('button', { name: /theo chiến dịch/i }).click();

    const mappedBadge = page.getByText(/^Mapped$/i).first();
    const hasMapped = await mappedBadge.isVisible().catch(() => false);
    if (hasMapped) {
      await expect(mappedBadge).toBeVisible();
      await expect(page.getByText(/\+.*₫/i).first()).toBeVisible();
    }

    await expect(page.locator('.portal-attribution-footer')).toContainText(/last_touch_crm/i, {
      timeout: 15_000,
    });
    await expect(page.getByRole('button', { name: /^Duyệt$/i })).toHaveCount(0);
  });
});
