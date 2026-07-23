import { createHmac } from 'crypto';
import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { pgReplicaReady } from './pg-contract-seed';

describe('Webhooks v1 (Phase 0 P0-4)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';
    process.env.PTT_WEBHOOKS_NEST_ENABLED = '1';
    process.env.PTT_WEBHOOKS_NEST_META = '1';
    process.env.PTT_WEBHOOKS_NEST_ZALO = '1';
    process.env.PTT_WEBHOOKS_NEST_GOOGLE = '1';
    process.env.PTT_WEBHOOKS_FLASK_FALLBACK = '0';
    process.env.PTT_JOBS_ENABLED = '1';
    process.env.PTT_WEBHOOK_V1_ENQUEUE = '1';
    process.env.CRM_FACEBOOK_VERIFY_TOKEN = 'test-meta-verify';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication({ rawBody: true });
    await app.init();
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  it('GET /api/v1/channels lists nest routing for meta/zalo/google', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer()).get('/api/v1/channels').expect(200);
    expect(res.body.channels).toContain('meta');
    expect(res.body.routing.meta).toBe('nest');
    expect(res.body.routing.zalo).toBe('nest');
    expect(res.body.routing.google).toBe('nest');
    expect(res.body.routing.default_fallback).toBe('none');
  });

  it('POST /api/v1/webhooks/zalo enqueues lead job', async () => {
    if (!app) return;
    const payload = {
      event_name: 'user_submit_info',
      oa_id: 'OA_001',
      info: { name: 'Zalo Nest', phone: '0907777666', campaign_id: 'Z1' },
    };
    const res = await request(app.getHttpServer())
      .post('/api/v1/webhooks/zalo')
      .set('Content-Type', 'application/json')
      .set('X-PTT-Client-Id', '550e8400-e29b-41d4-a716-446655440000')
      .send(payload)
      .expect(200);
    expect(res.body.verified).toBe(true);
    expect(res.body.accepted).toBe(true);
    expect(res.body.mode).toBe('queue');
    expect(res.body.handler).toBe('nest');
    expect(res.body.channel).toBe('zalo');
  });

  it('POST /api/v1/webhooks/google enqueues lead job', async () => {
    if (!app) return;
    const payload = {
      full_name: 'Google Nest',
      phone: '0906666555',
      email: 'google@test.local',
      meta: { google_lead_id: 'google-e2e-001' },
    };
    const res = await request(app.getHttpServer())
      .post('/api/v1/webhooks/google')
      .set('Content-Type', 'application/json')
      .set('X-PTT-Client-Id', '550e8400-e29b-41d4-a716-446655440000')
      .send(payload)
      .expect(200);
    expect(res.body.verified).toBe(true);
    expect(res.body.accepted).toBe(true);
    expect(res.body.mode).toBe('queue');
    expect(res.body.handler).toBe('nest');
    expect(res.body.channel).toBe('google');
  });

  it('GET /api/v1/webhooks/meta hub challenge', async () => {
    if (!app) return;
    await request(app.getHttpServer())
      .get('/api/v1/webhooks/meta')
      .query({
        'hub.mode': 'subscribe',
        'hub.verify_token': 'test-meta-verify',
        'hub.challenge': '12345',
      })
      .expect(200)
      .expect('12345');
  });

  it('POST /api/v1/webhooks/meta enqueues lead job', async () => {
    if (!app) return;
    const payload = {
      full_name: 'Webhook Nest',
      phone: '0908888777',
      email: 'nest@test.local',
      meta: { facebook_leadgen_id: 'nest-e2e-001' },
    };
    const body = Buffer.from(JSON.stringify(payload));
    const res = await request(app.getHttpServer())
      .post('/api/v1/webhooks/meta')
      .set('Content-Type', 'application/json')
      .set('X-PTT-Client-Id', '550e8400-e29b-41d4-a716-446655440000')
      .send(body)
      .expect(200);
    expect(res.body.verified).toBe(true);
    expect(res.body.accepted).toBe(true);
    expect(res.body.mode).toBe('queue');
    expect(res.body.job_ids?.length).toBeGreaterThan(0);
    expect(res.body.handler).toBe('nest');
    expect(res.body.resolved_client_id).toBe('550e8400-e29b-41d4-a716-446655440000');
  });

  it('POST /api/v1/webhooks/meta leadgen payload returns page_ids without Graph token', async () => {
    if (!app) return;
    const payload = {
      object: 'page',
      entry: [
        {
          id: '123456789012345',
          changes: [
            {
              field: 'leadgen',
              value: {
                leadgen_id: 'lg_b31_smoke_001',
                form_id: '2814926042203269',
                page_id: '123456789012345',
              },
            },
          ],
        },
      ],
    };
    const body = Buffer.from(JSON.stringify(payload));
    const res = await request(app.getHttpServer())
      .post('/api/v1/webhooks/meta')
      .set('Content-Type', 'application/json')
      .send(body)
      .expect(200);
    expect(res.body.verified).toBe(true);
    expect(res.body.handler).toBe('nest');
    expect(res.body.page_ids).toContain('123456789012345');
    expect(res.body.form_ids).toContain('2814926042203269');
  });
});
