import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import {
  E2E_CLIENT_ID,
  pgCapiEventLogReady,
  pgMetaConversionRulesReady,
  pgReplicaReady,
  seedE2eCapiEventLog,
  seedE2eConversionRules,
  seedE2eFailedCapiEventLog,
  seedE2eMetaChannelAccount,
} from './pg-contract-seed';

describe('Meta tracking B9 (health + capi events + test-pixel stub)', () => {
  let app: INestApplication;
  let staffToken = '';
  let channelAccountId = '';
  let failedCapiLogId = '';
  let clientRuleId = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady()) || !(await pgCapiEventLogReady())) {
      return;
    }
    channelAccountId = await seedE2eMetaChannelAccount();
    await seedE2eCapiEventLog();
    failedCapiLogId = await seedE2eFailedCapiEventLog();
    if (await pgMetaConversionRulesReady()) {
      clientRuleId = await seedE2eConversionRules();
    }

    process.env.PTT_META_TRACKING_ENABLED = '1';
    process.env.PTT_CAPI_STUB = '1';
    process.env.PTT_JOBS_ENABLED = '1';
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
    delete process.env.PTT_META_TRACKING_ENABLED;
    delete process.env.PTT_CAPI_STUB;
    delete process.env.PTT_JOBS_ENABLED;
    if (app) {
      await app.close();
    }
  });

  it('GET /meta/tracking/health returns rolling stats', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/meta/tracking/health?window_days=7')
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.attribution_model).toBe('last_touch_crm');
    expect(res.body.global).toBeDefined();
    expect(typeof res.body.global.sent).toBe('number');
    expect(Array.isArray(res.body.accounts)).toBe(true);
  });

  it('GET /meta/capi/events lists seeded rows', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/capi/events?client_id=${E2E_CLIENT_ID}`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(Array.isArray(res.body.events)).toBe(true);
    expect(res.body.count).toBeGreaterThan(0);
  });

  it('POST test-pixel returns stub ok', async () => {
    if (!app || !staffToken || !channelAccountId) return;
    const res = await request(app.getHttpServer())
      .post(
        `/api/v1/clients/${E2E_CLIENT_ID}/channel-accounts/${channelAccountId}/test-pixel`,
      )
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(201);

    expect(res.body.ok).toBe(true);
    expect(res.body.stub).toBe(true);
    expect(res.body.pixel_id).toBeTruthy();
  });

  it('GET /meta/conversion-rules lists seeded rules', async () => {
    if (!app || !staffToken || !clientRuleId) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/meta/conversion-rules?client_id=${E2E_CLIENT_ID}`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(Array.isArray(res.body.rules)).toBe(true);
    expect(res.body.rules.some((r: { id: string }) => r.id === clientRuleId)).toBe(true);
  });

  it('PATCH /meta/conversion-rules/:id updates enabled', async () => {
    if (!app || !staffToken || !clientRuleId) return;
    const res = await request(app.getHttpServer())
      .patch(`/api/v1/meta/conversion-rules/${clientRuleId}`)
      .set('Authorization', `Bearer ${staffToken}`)
      .send({ enabled: false, value_vnd: 50000 })
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.rule.enabled).toBe(false);
    expect(res.body.rule.value_vnd).toBe(50000);
  });

  it('POST /meta/capi/events/:id/retry resets failed row', async () => {
    if (!app || !staffToken || !failedCapiLogId) return;
    const res = await request(app.getHttpServer())
      .post(`/api/v1/meta/capi/events/${failedCapiLogId}/retry`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(201);

    expect(res.body.ok).toBe(true);
    expect(res.body.log_id).toBe(failedCapiLogId);
    expect(res.body.status).toBe('pending');
  });

  it('POST /meta/capi/flush processes flushable rows', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .post(`/api/v1/meta/capi/flush?client_id=${E2E_CLIENT_ID}&limit=10`)
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(201);

    expect(res.body.ok).toBe(true);
    expect(typeof res.body.processed).toBe('number');
    expect(Array.isArray(res.body.jobs)).toBe(true);
  });
});
