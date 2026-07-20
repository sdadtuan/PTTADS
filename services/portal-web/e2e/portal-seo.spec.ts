import { test, expect, type Page } from '@playwright/test';

const APPROVER_EMAIL = process.env.PORTAL_E2E_APPROVER_EMAIL ?? 'approver@demo.local';
const APPROVER_PASSWORD = process.env.PORTAL_E2E_APPROVER_PASSWORD ?? 'demo123';
const VIEWER_EMAIL = process.env.PORTAL_E2E_VIEWER_EMAIL ?? 'viewer@demo.local';
const VIEWER_PASSWORD = process.env.PORTAL_E2E_VIEWER_PASSWORD ?? 'demo123';
const API_URL = (process.env.PORTAL_E2E_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');
const CLIENT_ID = process.env.PORTAL_E2E_CLIENT_ID ?? '550e8400-e29b-41d4-a716-446655440000';
const INTERNAL_KEY =
  process.env.PORTAL_E2E_INTERNAL_KEY ??
  process.env.PTT_PORTAL_SEO_SERVICE_TOKEN ??
  process.env.PTT_CRM_INTERNAL_KEY ??
  'dev-portal-seo-internal';

async function login(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/mật khẩu|password/i).fill(password);
  await page.getByRole('button', { name: /đăng nhập|login/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

async function loginAsApprover(page: Page) {
  await login(page, APPROVER_EMAIL, APPROVER_PASSWORD);
}

async function loginAsViewer(page: Page) {
  await login(page, VIEWER_EMAIL, VIEWER_PASSWORD);
}

async function seedPendingContent(
  request: import('@playwright/test').APIRequestContext,
  title: string,
) {
  if (process.env.PORTAL_E2E_SKIP_HTTP_SEED === '1') {
    const envId = Number(process.env.PORTAL_E2E_SEO_CONTENT_ID || 0);
    return { id: envId, title };
  }
  // Legacy Flask seed — prefer PORTAL_E2E_SKIP_HTTP_SEED=1 + scripts/seed_portal_seo_e2e_content.py
  const flaskUrl = (process.env.PORTAL_E2E_FLASK_URL ?? 'http://127.0.0.1:5050').replace(/\/$/, '');
  const res = await request.post(`${flaskUrl}/api/v1/seo/internal/portal/e2e/seed-content`, {
    headers: {
      Authorization: `Bearer ${INTERNAL_KEY}`,
      'Content-Type': 'application/json',
    },
    data: {
      client_id: CLIENT_ID,
      customer_id: 1,
      title,
    },
  });
  expect(res.ok(), `seed content failed: ${res.status()} ${await res.text()}`).toBeTruthy();
  const body = (await res.json()) as { id: number; title: string };
  return body;
}

async function getPortalToken(request: import('@playwright/test').APIRequestContext) {
  const res = await request.post(`${API_URL}/api/v1/portal/auth/login`, {
    data: { email: APPROVER_EMAIL, password: APPROVER_PASSWORD },
  });
  expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as { access_token?: string; token?: string };
    const token = body.access_token ?? body.token;
    expect(token).toBeTruthy();
    return token as string;
}

test.describe('Portal SEO Phase 5C', () => {
  test('viewer: SEO dashboard + reports read-only', async ({ page }) => {
    await loginAsViewer(page);
    await page.getByRole('link', { name: /seo\/aeo/i }).click();
    await expect(page).toHaveURL(/\/seo$/);
    await expect(page.getByTestId('seo-widgets-panel')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('heading', { name: /SEO\/AEO KPI/i })).toBeVisible();

    await page.getByRole('link', { name: /seo reports/i }).click();
    await expect(page).toHaveURL(/\/seo\/reports/);
    await expect(page.getByRole('heading', { name: /Báo cáo SEO\/AEO/i })).toBeVisible({
      timeout: 15_000,
    });
  });

  test('viewer: pending list without approve buttons', async ({ page, request }) => {
    const title = process.env.PORTAL_E2E_VIEWER_SEO_TITLE ?? `E2E Viewer SEO ${Date.now()}`;
    await seedPendingContent(request, title);

    await loginAsViewer(page);
    await page.getByRole('link', { name: /seo review/i }).click();
    await expect(page).toHaveURL(/\/seo\/content/);
    await expect(page.getByText(title)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/viewer — chỉ xem/i)).toBeVisible();
    await page.getByRole('link', { name: title }).click();
    await expect(page.getByTestId('seo-approve-btn')).not.toBeVisible();
  });

  test('approver: client_review approve flow', async ({ page, request }) => {
    const title = process.env.PORTAL_E2E_SEO_TITLE ?? `E2E SEO Approve ${Date.now()}`;
    const seeded = await seedPendingContent(request, title);

    page.on('dialog', async (dialog) => {
      await dialog.accept('Playwright E2E approve');
    });

    await loginAsApprover(page);
    await page.getByRole('link', { name: /seo review/i }).click();
    await expect(page).toHaveURL(/\/seo\/content/);
    await expect(page.getByText(title)).toBeVisible({ timeout: 15_000 });

    await page.getByRole('link', { name: title }).click();
    await expect(page.getByTestId('seo-approve-btn')).toBeVisible();
    await page.getByTestId('seo-approve-btn').click();
    await expect(page).toHaveURL(/\/seo\/content/, { timeout: 15_000 });
    await expect(page.getByText(title)).not.toBeVisible({ timeout: 15_000 });

    const token = await getPortalToken(request);
    let contentId = seeded.id;
    if (!contentId) {
      const pending = await request.get(`${API_URL}/api/v1/portal/seo/content/pending`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const pendingBody = (await pending.json()) as { items?: Array<{ id: number; title: string }> };
      contentId = pendingBody.items?.find((i) => i.title === title)?.id ?? Number(process.env.PORTAL_E2E_SEO_CONTENT_ID || 0);
    }
    expect(contentId).toBeGreaterThan(0);
    const detail = await request.get(`${API_URL}/api/v1/portal/seo/content/${contentId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(detail.ok(), `content detail failed: ${detail.status()} ${await detail.text()}`).toBeTruthy();
    const body = (await detail.json()) as { workflow_status?: string };
    expect(body.workflow_status).toBe('approved');
  });
});
