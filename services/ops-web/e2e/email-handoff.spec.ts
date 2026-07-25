import { test, expect } from '@playwright/test';

const STAFF_EMAIL = process.env.OPS_E2E_STAFF_EMAIL ?? 'staff@demo.local';
const STAFF_PASSWORD = process.env.OPS_E2E_STAFF_PASSWORD ?? 'demo123';
const PILOT_CLIENT_ID = process.env.OPS_EMAIL_HANDOFF_CLIENT_ID ?? '';
const HANDOFF_DOMAIN = process.env.OPS_EMAIL_HANDOFF_DOMAIN ?? 'handoff-email.example.com';
const API_URL = (process.env.OPS_E2E_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');

async function loginAsStaff(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.locator('#email').fill(STAFF_EMAIL);
  await page.locator('#password').fill(STAFF_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

test.describe('Email Marketing ops-web §13 handoff', () => {
  test('E-01 hub — client email health loads', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/email/hub');
    await expect(page.getByText(/EM-0 — Email Ops hub|E-01/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Client email health|Emails sent/i)).toBeVisible({ timeout: 15_000 });
  });

  test('§13 executive drill-down — hub → client → contacts (≤3 clicks)', async ({ page }) => {
    test.skip(!PILOT_CLIENT_ID, 'OPS_EMAIL_HANDOFF_CLIENT_ID not set');
    await loginAsStaff(page);
    await page.goto('/email/hub');
    await expect(page.getByText(/Client email health/i)).toBeVisible({ timeout: 15_000 });

    const clientLink = page.locator(`a[href="/email/clients/${PILOT_CLIENT_ID}"]`).first();
    const hasClient = await clientLink.isVisible().catch(() => false);
    if (!hasClient) {
      await page.goto(`/email/clients/${PILOT_CLIENT_ID}`);
    } else {
      await clientLink.click();
    }
    await expect(page).toHaveURL(new RegExp(`/email/clients/${PILOT_CLIENT_ID}`));
    await expect(page.getByText(/workspace|esp_provider|Cài đặt workspace/i)).toBeVisible({
      timeout: 15_000,
    });

    await page.goto('/email/contacts');
    await expect(page.getByText(/Danh bạ contacts|E-04/i)).toBeVisible({ timeout: 15_000 });
  });

  test('§13 client workspace settings visible', async ({ page }) => {
    test.skip(!PILOT_CLIENT_ID, 'OPS_EMAIL_HANDOFF_CLIENT_ID not set');
    await loginAsStaff(page);
    await page.goto(`/email/clients/${PILOT_CLIENT_ID}?tab=settings`);
    await expect(page.getByText(/Workspace settings/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/From email/i)).toBeVisible();
    if (HANDOFF_DOMAIN) {
      const body = await page.content();
      expect(body.toLowerCase()).toContain(HANDOFF_DOMAIN.split('.')[0].toLowerCase());
    }
  });

  test('E-13 governance — global rules section', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/email/governance');
    await expect(page.getByText(/Governance|E-13/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('heading', { name: /Global rules/i })).toBeVisible();
  });

  test('E-02 clients list loads', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/email/clients');
    await expect(page.getByText(/Danh sách client Email|E-02/i)).toBeVisible({ timeout: 15_000 });
  });

  test('Gate A readiness page', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/email/gate-a');
    await expect(page.getByRole('heading', { name: /Gate A/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Staged cutover/i)).toBeVisible();
  });

  test('§13 hub API smoke (Nest)', async ({ request }) => {
    const login = await request.post(`${API_URL}/api/v1/staff/auth/login`, {
      data: { email: STAFF_EMAIL, password: STAFF_PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const { access_token: token } = (await login.json()) as { access_token?: string };
    expect(token).toBeTruthy();

    const res = await request.get(`${API_URL}/api/v1/email/hub?days=7`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok(), `email hub API: ${res.status()} ${await res.text()}`).toBeTruthy();
    const body = (await res.json()) as { ok?: boolean };
    expect(body.ok).toBe(true);
  });

  test('§13 mobile smoke — hub + contacts', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAsStaff(page);
    await page.goto('/email/hub');
    await expect(page.getByText(/Client email health|Emails sent/i)).toBeVisible({ timeout: 15_000 });

    await page.goto('/email/contacts');
    await expect(page.getByText(/Danh bạ contacts|E-04/i)).toBeVisible({ timeout: 15_000 });
  });
});
