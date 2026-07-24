import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { pgFacebookHubReady, pgReplicaReady, seedE2eDailyPerformance } from './pg-contract-seed';

describe('Facebook hub B8 (attribution + campaigns + sync)', () => {
  let app: INestApplication;
  let staffToken = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady()) || !(await pgFacebookHubReady())) {
      return;
    }
    await seedE2eDailyPerformance();
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
    if (app) {
      await app.close();
    }
  });

  it('GET /facebook-ads/hub includes attribution block', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/facebook-ads/hub?days=7')
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.attribution).toBeDefined();
    expect(res.body.attribution.attribution_model).toBe('last_touch_crm');
    expect(typeof res.body.attribution.unmapped_spend_pct).toBe('number');
    expect(res.body.summary.unmapped_spend_pct).toBeDefined();
  });

  it('GET /facebook-ads/hub/campaigns returns campaign rows with CPL delta', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/facebook-ads/hub/campaigns?days=7')
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(Array.isArray(res.body.campaigns)).toBe(true);
    expect(res.body.attribution?.attribution_model).toBe('last_touch_crm');
    if (res.body.campaigns.length > 0) {
      const row = res.body.campaigns[0];
      expect(row).toHaveProperty('hub_mapped');
      expect(row).toHaveProperty('cpl_delta_vnd');
    }
  });

  it('GET /meta/sync/status returns global sync chip fields', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/meta/sync/status')
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.global).toBeDefined();
    expect(['ok', 'warn', 'error']).toContain(res.body.global.status);
    expect(Array.isArray(res.body.clients)).toBe(true);
  });
});
