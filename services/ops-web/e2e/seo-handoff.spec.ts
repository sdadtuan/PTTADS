import { test, expect } from '@playwright/test';

const STAFF_EMAIL = process.env.OPS_E2E_STAFF_EMAIL ?? 'staff@demo.local';
const STAFF_PASSWORD = process.env.OPS_E2E_STAFF_PASSWORD ?? 'demo123';
const PILOT_CUSTOMER_ID = process.env.OPS_SEO_HANDOFF_CUSTOMER_ID ?? '1';
const HANDOFF_DOMAIN = process.env.OPS_SEO_HANDOFF_DOMAIN ?? 'handoff-e2e.example.com';
const API_URL = (process.env.OPS_E2E_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');

async function loginAsStaff(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.locator('#email').fill(STAFF_EMAIL);
  await page.locator('#password').fill(STAFF_PASSWORD);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

test.describe('SEO/AEO ops-web §12 handoff', () => {
  test('S-01 hub — executive overview loads', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/seo/hub');
    await expect(page.getByRole('heading', { name: 'SEO/AEO Hub' })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Clients overview|GSC trend/i)).toBeVisible({ timeout: 15_000 });
  });

  test('§12 executive drill-down — hub → client → content (≤3 clicks)', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/seo/hub');
    await expect(page.getByText('Clients overview')).toBeVisible({ timeout: 15_000 });

    const clientLink = page.locator(`a[href="/seo/clients/${PILOT_CUSTOMER_ID}"]`).first();
    const hasClient = await clientLink.isVisible().catch(() => false);
    if (!hasClient) {
      await page.goto(`/seo/clients/${PILOT_CUSTOMER_ID}`);
    } else {
      await clientLink.click();
    }
    await expect(page).toHaveURL(new RegExp(`/seo/clients/${PILOT_CUSTOMER_ID}`));
    await expect(page.getByText(/Health|AEO coverage/i)).toBeVisible({ timeout: 15_000 });

    await page.goto(`/seo/content?customer_id=${PILOT_CUSTOMER_ID}`);
    await expect(page.getByRole('heading', { name: /Nội dung — Pipeline/i })).toBeVisible({
      timeout: 15_000,
    });
  });

  test('§12 client settings → workspace visible', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`/seo/clients/${PILOT_CUSTOMER_ID}?tab=settings`);
    await expect(page.getByText(/Client settings \(S-04\)/i)).toBeVisible({ timeout: 15_000 });

    const domainArea = page.locator('textarea').first();
    await expect(domainArea).toBeVisible();
    const current = await domainArea.inputValue();
    expect(current).toContain(HANDOFF_DOMAIN.split('.')[0]);

    await page.getByRole('button', { name: /Tổng quan/i }).click();
    await expect(page.getByText(/Integrations|Content delivery/i)).toBeVisible({ timeout: 15_000 });
  });

  test('S-09 technical — CWV panel section', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`/seo/technical?customer_id=${PILOT_CUSTOMER_ID}`);
    await expect(page.getByRole('heading', { name: /Technical|Kỹ thuật/i })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole('button', { name: /Capture CWV/i })).toBeVisible();
  });

  test('S-06 research console loads', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`/seo/research?customer_id=${PILOT_CUSTOMER_ID}`);
    await expect(page.getByRole('heading', { name: /Nghiên cứu SEO\/AEO/i })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole('button', { name: /Keywords/i })).toBeVisible();
  });

  test('Gate A readiness page', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto('/seo/gate-a');
    await expect(page.getByRole('heading', { name: /Gate A/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Staged cutover/i)).toBeVisible();
  });

  test('§12 attribution API smoke (Nest)', async ({ request }) => {
    const login = await request.post(`${API_URL}/api/v1/staff/auth/login`, {
      data: { email: STAFF_EMAIL, password: STAFF_PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const { access_token: token } = (await login.json()) as { access_token?: string };
    expect(token).toBeTruthy();

    const res = await request.get(
      `${API_URL}/api/v1/seo/bi/attribution?customer_id=${PILOT_CUSTOMER_ID}&days=28`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(res.ok(), `attribution API: ${res.status()} ${await res.text()}`).toBeTruthy();
    const body = (await res.json()) as { ok?: boolean };
    expect(body.ok).toBe(true);
  });

  test('§12 mobile smoke — hub + content list', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAsStaff(page);
    await page.goto('/seo/hub');
    await expect(page.getByText(/Clients overview|GSC trend/i)).toBeVisible({ timeout: 15_000 });

    await page.goto(`/seo/content?customer_id=${PILOT_CUSTOMER_ID}`);
    await expect(page.getByRole('heading', { name: /Nội dung — Pipeline/i })).toBeVisible({
      timeout: 15_000,
    });
  });
});
