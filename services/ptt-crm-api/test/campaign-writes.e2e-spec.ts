import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { Pool } from 'pg';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import {
  ensureE2eTestClient,
  pgCampaignWritesTableReady,
  pgReplicaReady,
} from './pg-contract-seed';

const DATABASE_URL =
  process.env.DATABASE_URL ??
  process.env.PTT_DATABASE_URL ??
  'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency';

const E2E_CLIENT_ID = '550e8400-e29b-41d4-a716-446655440000';

describe('Campaign writes API (Phase 4 F1)', () => {
  let app: INestApplication;
  let pendingId = '';
  let rejectId = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady()) || !(await pgCampaignWritesTableReady())) {
      return;
    }
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication();
    await app.init();
    await ensureE2eTestClient();
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  it('POST /api/v1/campaign-writes creates pending row', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer())
      .post('/api/v1/campaign-writes')
      .send({
        client_id: E2E_CLIENT_ID,
        external_campaign_id: '120210123456789',
        external_campaign_name: 'E2E Budget Test',
        change_type: 'daily_budget',
        new_value: { daily_budget_vnd: 450000 },
        submitted_by: 'am@test.local',
      })
      .expect(201);
    expect(res.body.ok).toBe(true);
    expect(res.body.request.status).toBe('pending_approval');
    expect(res.body.workflow_id).toMatch(/^campaign-write-/);
    pendingId = res.body.request.id;

    const pool = new Pool({ connectionString: DATABASE_URL });
    try {
      const ev = await pool.query(
        `SELECT event_type, idempotency_key FROM domain_events
         WHERE aggregate_type = 'campaign_write' AND aggregate_id = $1
         ORDER BY created_at DESC LIMIT 1`,
        [pendingId],
      );
      expect(ev.rows[0]?.event_type).toBe('CampaignWriteSubmitted');
      expect(ev.rows[0]?.idempotency_key).toBe(`campaign-write:${pendingId}:submitted`);
    } finally {
      await pool.end();
    }
  });

  it('GET /api/v1/campaign-writes/pending lists client rows', async () => {
    if (!app || !pendingId) return;
    const res = await request(app.getHttpServer())
      .get(`/api/v1/campaign-writes/pending?client_id=${E2E_CLIENT_ID}`)
      .expect(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.count).toBeGreaterThan(0);
    expect(res.body.rows.some((r: { id: string }) => r.id === pendingId)).toBe(true);
  });

  it('POST reject updates status', async () => {
    if (!app) return;
    const submit = await request(app.getHttpServer())
      .post('/api/v1/campaign-writes')
      .send({
        client_id: E2E_CLIENT_ID,
        external_campaign_id: '120210999999999',
        change_type: 'daily_budget',
        new_value: { daily_budget_vnd: 100000 },
        submitted_by: 'am@test.local',
      })
      .expect(201);
    rejectId = submit.body.request.id;

    const res = await request(app.getHttpServer())
      .post(`/api/v1/campaign-writes/${rejectId}/reject`)
      .send({ approved_by: 'admin@test.local', note: 'no' })
      .expect(201);
    expect(res.body.ok).toBe(true);
    expect(res.body.request.status).toBe('rejected');
  });

  it('POST approve emits CampaignWriteApproved', async () => {
    if (!app || !pendingId) return;
    const res = await request(app.getHttpServer())
      .post(`/api/v1/campaign-writes/${pendingId}/approve`)
      .send({ approved_by: 'admin@test.local', note: 'ok' })
      .expect(201);
    expect(res.body.ok).toBe(true);
    expect(res.body.request.status).toBe('approved');
    expect(res.body.temporal_signal).toBe('stub');

    const pool = new Pool({ connectionString: DATABASE_URL });
    try {
      const ev = await pool.query(
        `SELECT event_type, idempotency_key FROM domain_events
         WHERE aggregate_type = 'campaign_write' AND aggregate_id = $1
           AND event_type = 'CampaignWriteApproved'
         ORDER BY created_at DESC LIMIT 1`,
        [pendingId],
      );
      expect(ev.rows[0]?.event_type).toBe('CampaignWriteApproved');
      expect(ev.rows[0]?.idempotency_key).toBe(`campaign-write:${pendingId}:approved`);
    } finally {
      await pool.end();
    }
  });

  it('POST approve on non-pending returns 400', async () => {
    if (!app || !pendingId) return;
    await request(app.getHttpServer())
      .post(`/api/v1/campaign-writes/${pendingId}/approve`)
      .send({ approved_by: 'admin@test.local' })
      .expect(400);
  });
});
