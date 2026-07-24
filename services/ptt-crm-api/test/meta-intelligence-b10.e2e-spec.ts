import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { E2E_CLIENT_ID, pgReplicaReady } from './pg-contract-seed';

describe('Meta intelligence B10 (anomalies + roas + budget-recommendations)', () => {
  let app: INestApplication;
  let staffToken = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }

    process.env.PTT_META_ANOMALY_ENABLED = '1';
    process.env.PTT_META_ROAS_ENABLED = '1';
    process.env.PTT_STAFF_JWT_SECRET = 'test-staff-secret-phase0-min-len-32';
    process.env.PTT_STAFF_STUB_USERS =
      'staff@demo.local:demo123:staff-demo-1:1:Demo Staff';
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication();
    await app.init();

    const login = await request(app.getHttpServer())
      .post('/api/v1/staff/auth/login')
      .send({ email: 'staff@demo.local', password: 'demo123' })
      .expect(200);
    staffToken = login.body.access_token;
  });

  afterAll(async () => {
    delete process.env.PTT_META_ANOMALY_ENABLED;
    delete process.env.PTT_META_ROAS_ENABLED;
    if (app) {
      await app.close();
    }
  });

  it('GET /meta/anomalies returns attribution metadata', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/anomalies?client_id=${E2E_CLIENT_ID}&days=7`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(Array.isArray(res.body.anomalies)).toBe(true);
    expect(res.body.attribution.attribution_model).toBe('last_touch_crm');
  });

  it('GET /meta/roas returns series + summary', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/roas?client_id=${E2E_CLIENT_ID}&days=7`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.summary).toBeDefined();
    expect(Array.isArray(res.body.series)).toBe(true);
    expect(res.body.attribution.spend_source).toBe('meta_api');
  });

  it('GET /meta/budget-recommendations is read-only', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/budget-recommendations?client_id=${E2E_CLIENT_ID}`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.read_only).toBe(true);
    expect(Array.isArray(res.body.recommendations)).toBe(true);
  });

  it('GET /meta/insights/daily returns campaign rows', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/insights/daily?client_id=${E2E_CLIENT_ID}&level=campaign&days=7`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.level).toBe('campaign');
    expect(Array.isArray(res.body.rows)).toBe(true);
    expect(res.body.attribution.attribution_model).toBe('last_touch_crm');
  });

  it('GET /meta/insights/daily?level=adset respects enabled level', async () => {
    if (!app || !staffToken) return;
    process.env.PTT_META_INSIGHTS_LEVEL = 'adset';
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/insights/daily?client_id=${E2E_CLIENT_ID}&level=adset&days=7`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.level).toBe('adset');
    expect(Array.isArray(res.body.rows)).toBe(true);
    delete process.env.PTT_META_INSIGHTS_LEVEL;
  });
});
