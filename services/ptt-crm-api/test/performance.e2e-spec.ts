import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import {
  pgPerformanceTableReady,
  pgReplicaReady,
  seedE2eDailyPerformance,
} from './pg-contract-seed';

describe('Performance API (portal JWT)', () => {
  let app: INestApplication;
  let token = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady()) || !(await pgPerformanceTableReady())) {
      return;
    }
    await seedE2eDailyPerformance();
    process.env.PTT_PORTAL_JWT_SECRET = 'test-portal-secret-sprint0-min-len';
    process.env.PTT_PORTAL_STUB_USERS =
      'viewer@test.local:pass123:550e8400-e29b-41d4-a716-446655440000:viewer';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication();
    await app.init();

    const login = await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email: 'viewer@test.local', password: 'pass123' })
      .expect(200);
    token = login.body.access_token;
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  it('GET /api/v1/performance requires Bearer', async () => {
    if (!app) return;
    await request(app.getHttpServer()).get('/api/v1/performance').expect(401);
  });

  it('GET /api/v1/performance returns scoped rows', async () => {
    if (!app || !token) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/performance')
      .set('Authorization', `Bearer ${token}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.client_id).toBe('550e8400-e29b-41d4-a716-446655440000');
    expect(Array.isArray(res.body.rows)).toBe(true);
    expect(res.body.rows.length).toBeGreaterThan(0);
    expect(res.body.summary.total_spend).toBeGreaterThan(0);
    expect(res.body.summary.total_leads_crm).toBeGreaterThan(0);
    expect(res.body.rows[0].external_campaign_id).toBe('camp_e2e');
  });

  it('GET /api/v1/performance rejects client_id mismatch', async () => {
    if (!app || !token) return;
    await request(app.getHttpServer())
      .get('/api/v1/performance')
      .query({ client_id: '00000000-0000-0000-0000-000000000001' })
      .set('Authorization', `Bearer ${token}`)
      .expect(403);
  });

  it('GET /api/v1/performance?channel=meta filters Meta rows', async () => {
    if (!app || !token) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/performance')
      .query({ channel: 'meta' })
      .set('Authorization', `Bearer ${token}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.channel).toBe('meta');
    expect(res.body.rows.length).toBeGreaterThan(0);
    expect(res.body.rows.every((row: { channel: string }) => row.channel === 'meta')).toBe(true);
  });
});
