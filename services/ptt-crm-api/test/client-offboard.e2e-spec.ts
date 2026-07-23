import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { Pool } from 'pg';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import {
  E2E_CLIENT_ID,
  pgClientOffboardReady,
  pgReplicaReady,
  resetE2eClientActive,
} from './pg-contract-seed';

const DATABASE_URL =
  process.env.DATABASE_URL ??
  process.env.PTT_DATABASE_URL ??
  'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency';

describe('Client offboard (B7.1-S3)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    if (!(await pgReplicaReady()) || !(await pgClientOffboardReady())) {
      return;
    }
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';
    process.env.PTT_JOBS_ENABLED = '1';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication();
    await app.init();
    await resetE2eClientActive();
  });

  afterAll(async () => {
    if (app) {
      await resetE2eClientActive().catch(() => undefined);
      await app.close();
    }
  });

  it('POST offboard archives client and writes audit', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer())
      .post(`/api/v1/clients/${E2E_CLIENT_ID}/offboard`)
      .send({ reason: 'other', note: 'e2e-b7-s3' })
      .expect(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.status).toBe('archived');
    expect(res.body.tenant_locked).toBe(true);
    expect(res.body.audit_id).toBeTruthy();
    expect(res.body.follow_up).toBeDefined();

    const audit = await request(app.getHttpServer())
      .get(`/api/v1/clients/${E2E_CLIENT_ID}/offboard/audit`)
      .expect(200);
    expect(audit.body.rows?.length).toBeGreaterThan(0);
  });

  it('POST offboard is idempotent', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer())
      .post(`/api/v1/clients/${E2E_CLIENT_ID}/offboard`)
      .send({ reason: 'other' })
      .expect(200);
    expect(res.body.idempotent).toBe(true);
  });

  it('PATCH client blocked with tenant_archived', async () => {
    if (!app) return;
    await request(app.getHttpServer())
      .patch(`/api/v1/clients/${E2E_CLIENT_ID}`)
      .send({ notes: 'blocked' })
      .expect(403)
      .expect(({ body }) => {
        expect(body.error).toBe('tenant_archived');
      });
  });

  it('portal login blocked for archived tenant', async () => {
    if (!app) return;
    process.env.PTT_PORTAL_JWT_SECRET = 'test-portal-secret-sprint0-min-len';
    process.env.PTT_PORTAL_STUB_USERS =
      'viewer@test.local:pass123:550e8400-e29b-41d4-a716-446655440000:viewer';

    await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email: 'viewer@test.local', password: 'pass123' })
      .expect(403)
      .expect(({ body }) => {
        expect(body.error).toBe('tenant_archived');
      });
  });

  it('cancels pending agency jobs on offboard', async () => {
    if (!app) return;
    await resetE2eClientActive();
    const pool = new Pool({ connectionString: DATABASE_URL });
    let jobId = '';
    try {
      const insert = await pool.query(
        `INSERT INTO job_queue (job_type, payload, idempotency_key, client_id, status)
         VALUES ('meta_insights_sync', '{}'::jsonb, $2, $1::uuid, 'pending')
         RETURNING id::text`,
        [E2E_CLIENT_ID, `e2e-offboard-job-${Date.now()}`],
      );
      jobId = String(insert.rows[0]?.id ?? '');
    } finally {
      await pool.end();
    }

    await request(app.getHttpServer())
      .post(`/api/v1/clients/${E2E_CLIENT_ID}/offboard`)
      .send({ reason: 'churn' })
      .expect(200);

    const pool2 = new Pool({ connectionString: DATABASE_URL });
    try {
      const row = await pool2.query(`SELECT status, last_error FROM job_queue WHERE id = $1::uuid`, [
        jobId,
      ]);
      expect(row.rows[0]?.status).toBe('dead');
      expect(String(row.rows[0]?.last_error ?? '')).toContain('client_offboarded');
    } finally {
      await pool2.end();
    }
  });
});
