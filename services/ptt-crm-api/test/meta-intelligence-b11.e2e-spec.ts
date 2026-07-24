import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { E2E_CLIENT_ID, pgReplicaReady } from './pg-contract-seed';

describe('Meta intelligence B11 (stat anomalies + forecast + pixels + snapshot)', () => {
  let app: INestApplication;
  let staffToken = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }

    process.env.PTT_META_ANOMALY_STAT_ENABLED = '1';
    process.env.PTT_META_FORECAST_ENABLED = '1';
    process.env.PTT_META_PIXELS_ENABLED = '1';
    process.env.PTT_META_INTEL_SNAPSHOT_ENABLED = '1';
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
    delete process.env.PTT_META_ANOMALY_STAT_ENABLED;
    delete process.env.PTT_META_FORECAST_ENABLED;
    delete process.env.PTT_META_PIXELS_ENABLED;
    delete process.env.PTT_META_INTEL_SNAPSHOT_ENABLED;
    if (app) {
      await app.close();
    }
  });

  it('GET /meta/anomalies?mode=stat returns stat mode', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/anomalies?client_id=${E2E_CLIENT_ID}&mode=stat&days=14`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.mode).toBe('stat');
    expect(Array.isArray(res.body.anomalies)).toBe(true);
  });

  it('GET /meta/forecast returns slope + projection', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/forecast?client_id=${E2E_CLIENT_ID}&metric=cpl&days=14`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(typeof res.body.slope).toBe('number');
    expect(Array.isArray(res.body.projection)).toBe(true);
    expect(res.body.projection.length).toBeGreaterThan(0);
  });

  it('GET /meta/pixels lists pixels or disabled hint', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/pixels?client_id=${E2E_CLIENT_ID}`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(Array.isArray(res.body.pixels)).toBe(true);
  });

  it('POST /meta/intelligence/snapshot creates snapshot or not-ready hint', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .post('/api/v1/meta/intelligence/snapshot')
      .set('Authorization', `Bearer ${staffToken}`)
      .send({ client_id: E2E_CLIENT_ID, days: 7 });

    expect([200, 201]).toContain(res.status);
    expect(res.body.ok === true || res.body.reason != null).toBe(true);
  });
});
