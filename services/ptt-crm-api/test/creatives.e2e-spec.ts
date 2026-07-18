import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { Pool } from 'pg';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import {
  pgCreativesTableReady,
  pgReplicaReady,
} from './pg-contract-seed';

const DATABASE_URL =
  process.env.DATABASE_URL ??
  process.env.PTT_DATABASE_URL ??
  'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency';

describe('Creatives API (portal P4)', () => {
  let app: INestApplication;
  let approverToken = '';
  let viewerToken = '';
  let pendingId = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady()) || !(await pgCreativesTableReady())) {
      return;
    }
    process.env.PTT_PORTAL_JWT_SECRET = 'test-portal-secret-sprint0-min-len';
    process.env.PTT_PORTAL_STUB_USERS =
      'viewer@test.local:pass123:550e8400-e29b-41d4-a716-446655440000:viewer,' +
      'approver@test.local:pass123:550e8400-e29b-41d4-a716-446655440000:approver';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication();
    await app.init();

    const viewerLogin = await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email: 'viewer@test.local', password: 'pass123' })
      .expect(200);
    viewerToken = viewerLogin.body.access_token;

    const approverLogin = await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email: 'approver@test.local', password: 'pass123' })
      .expect(200);
    approverToken = approverLogin.body.access_token;
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  it('POST /api/v1/creatives submit creates pending row', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer())
      .post('/api/v1/creatives')
      .send({
        client_id: '550e8400-e29b-41d4-a716-446655440000',
        title: 'E2E Submit Test',
        version: 1,
        submitted_by: 'am@test.local',
      })
      .expect(201);
    expect(res.body.ok).toBe(true);
    expect(res.body.creative.status).toBe('pending_client');
    expect(res.body.workflow_id).toMatch(/^creative-approval-/);
    pendingId = res.body.creative.id;
  });

  it('GET /api/v1/creatives/pending lists scoped rows', async () => {
    if (!app || !viewerToken) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/creatives/pending')
      .set('Authorization', `Bearer ${viewerToken}`)
      .expect(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.count).toBeGreaterThan(0);
    expect(res.body.rows[0].status).toBe('pending_client');
  });

  it('POST approve forbidden for viewer role', async () => {
    if (!app || !viewerToken || !pendingId) return;
    await request(app.getHttpServer())
      .post(`/api/v1/creatives/${pendingId}/approve`)
      .set('Authorization', `Bearer ${viewerToken}`)
      .expect(403);
  });

  it('POST approve rejects cross-tenant creative id', async () => {
    if (!app || !approverToken) return;
    const OTHER_CLIENT = '660e8400-e29b-41d4-a716-446655440001';
    const pool = new Pool({ connectionString: DATABASE_URL });
    let otherId = '';
    try {
      await pool.query(
        `INSERT INTO clients (id, code, name, status)
         VALUES ($1::uuid, 'E2E_OTHER', 'Other Tenant', 'active')
         ON CONFLICT (id) DO NOTHING`,
        [OTHER_CLIENT],
      );
      const ins = await pool.query(
        `INSERT INTO creative_submissions (
           client_id, title, version, status, submitted_by, submitted_at
         ) VALUES ($1::uuid, 'Cross tenant trap', 1, 'pending_client', 'am@test.local', NOW())
         RETURNING id::text`,
        [OTHER_CLIENT],
      );
      otherId = String(ins.rows[0]?.id ?? '');
    } finally {
      await pool.end();
    }
    if (!otherId) return;
    await request(app.getHttpServer())
      .post(`/api/v1/creatives/${otherId}/approve`)
      .set('Authorization', `Bearer ${approverToken}`)
      .expect(403);
  });

  it('GET pending never leaks other client rows', async () => {
    if (!app || !approverToken) return;
    const res = await request(app.getHttpServer())
      .get('/api/v1/creatives/pending')
      .set('Authorization', `Bearer ${approverToken}`)
      .expect(200);
    for (const row of res.body.rows ?? []) {
      expect(row.client_id).toBe('550e8400-e29b-41d4-a716-446655440000');
    }
  });

  it('POST approve emits CreativeApproved for approver', async () => {
    if (!app || !approverToken || !pendingId) return;
    const res = await request(app.getHttpServer())
      .post(`/api/v1/creatives/${pendingId}/approve`)
      .set('Authorization', `Bearer ${approverToken}`)
      .expect(201);
    expect(res.body.ok).toBe(true);
    expect(res.body.creative.status).toBe('approved');
    expect(res.body.temporal_signal).toBe('stub');

    const pool = new Pool({ connectionString: DATABASE_URL });
    try {
      const ev = await pool.query(
        `SELECT event_type, idempotency_key FROM domain_events
         WHERE aggregate_type = 'creative' AND aggregate_id = $1
         ORDER BY created_at DESC LIMIT 1`,
        [pendingId],
      );
      expect(ev.rows[0]?.event_type).toBe('CreativeApproved');
      expect(ev.rows[0]?.idempotency_key).toBe(`creative:${pendingId}:approved:v1`);
    } finally {
      await pool.end();
    }
  });
});
