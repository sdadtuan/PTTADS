import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { pgReplicaReady, ensureE2eTestClient } from './pg-contract-seed';

async function writeTestsEnabled(): Promise<boolean> {
  if (!(await pgReplicaReady())) {
    return false;
  }
  await ensureE2eTestClient();
  process.env.PTT_LEADS_READ_SOURCE = 'pg';
  process.env.PTT_LEADS_WRITE_ENABLED = '1';
  process.env.PTT_CRM_API_AUTH_DISABLED = '1';
  return true;
}

describe('Leads API v1 write staging (e2e B9)', () => {
  let app: INestApplication;
  let skip = false;
  let createdLeadId = 0;

  beforeAll(async () => {
    if (!(await writeTestsEnabled())) {
      skip = true;
      return;
    }
    process.env.PORT = '0';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  it('GET /health reports write enabled', async () => {
    if (skip) return;
    await request(app.getHttpServer())
      .get('/health')
      .expect(200)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body.leads_write_enabled).toBe(true);
      });
  });

  it('POST /api/v1/leads creates staging stub', async () => {
    if (skip) return;
    process.env.PTT_LEADS_CREATE_ID_MODE = 'staging';
    const res = await request(app.getHttpServer())
      .post('/api/v1/leads')
      .send({
        full_name: 'B9 Staging Lead',
        phone: '0904444444',
        channel: 'meta',
        client_id: '550e8400-e29b-41d4-a716-446655440000',
        status: 'new',
        source: 'staging',
      })
      .expect(201);
    expect(res.body.full_name).toBe('B9 Staging Lead');
    expect(res.body.id).toBeGreaterThanOrEqual(900_000_000);
    createdLeadId = res.body.id;

    const { Pool } = await import('pg');
    const pool = new Pool({
      connectionString:
        process.env.DATABASE_URL ??
        'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency',
    });
    try {
      const ev = await pool.query(
        `SELECT event_type, idempotency_key FROM domain_events
         WHERE aggregate_type = 'lead' AND aggregate_id = $1 AND event_type = 'LeadCreated'
         ORDER BY created_at DESC LIMIT 1`,
        [String(createdLeadId)],
      );
      expect(ev.rows.length).toBeGreaterThan(0);
      expect(ev.rows[0].idempotency_key).toBe(`lead:${createdLeadId}:created`);
    } finally {
      await pool.end();
    }
  });

  it('PATCH /api/v1/leads/:id assign emits LeadAssigned', async () => {
    if (skip || !createdLeadId) return;
    const res = await request(app.getHttpServer())
      .patch(`/api/v1/leads/${createdLeadId}`)
      .send({ owner_id: 42, assigned_by: 'e2e-test' })
      .expect(200);
    expect(res.body.owner_id).toBe(42);

    const { Pool } = await import('pg');
    const pool = new Pool({
      connectionString:
        process.env.DATABASE_URL ??
        'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency',
    });
    try {
      const ev = await pool.query(
        `SELECT event_type, payload, idempotency_key FROM domain_events
         WHERE aggregate_type = 'lead' AND aggregate_id = $1 AND event_type = 'LeadAssigned'
         ORDER BY created_at DESC LIMIT 1`,
        [String(createdLeadId)],
      );
      expect(ev.rows.length).toBeGreaterThan(0);
      expect(ev.rows[0].payload.owner_id).toBe(42);
      expect(ev.rows[0].idempotency_key).toBe(`lead:${createdLeadId}:assigned:42`);
    } finally {
      await pool.end();
    }
  });

  it('PATCH assign idempotent — re-assign same owner once', async () => {
    if (skip || !createdLeadId) return;
    await request(app.getHttpServer())
      .patch(`/api/v1/leads/${createdLeadId}`)
      .send({ owner_id: 55, assigned_by: 'e2e-idem-alt' })
      .expect(200);
    await request(app.getHttpServer())
      .patch(`/api/v1/leads/${createdLeadId}`)
      .send({ owner_id: 42, assigned_by: 'e2e-idem' })
      .expect(200);
    await request(app.getHttpServer())
      .patch(`/api/v1/leads/${createdLeadId}`)
      .send({ owner_id: 42, assigned_by: 'e2e-idem-dup' })
      .expect(200);

    const { Pool } = await import('pg');
    const pool = new Pool({
      connectionString:
        process.env.DATABASE_URL ??
        'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency',
    });
    try {
      const ev = await pool.query(
        `SELECT COUNT(*)::int AS n FROM domain_events
         WHERE event_type = 'LeadAssigned'
           AND idempotency_key = $1`,
        [`lead:${createdLeadId}:assigned:42`],
      );
      expect(ev.rows[0]?.n).toBe(1);
    } finally {
      await pool.end();
    }
  });

  it('PATCH /api/v1/leads/:id score stub', async () => {
    if (skip || !createdLeadId) return;
    await request(app.getHttpServer())
      .patch(`/api/v1/leads/${createdLeadId}`)
      .send({ score: 88 })
      .expect(200);
  });

  it('POST /api/v1/leads prod mode uses id below 900M when sequence ready', async () => {
    if (skip) return;
    const prev = process.env.PTT_LEADS_CREATE_ID_MODE;
    process.env.PTT_LEADS_CREATE_ID_MODE = 'prod';
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    const prodApp = moduleFixture.createNestApplication();
    await prodApp.init();
    try {
      const res = await request(prodApp.getHttpServer())
        .post('/api/v1/leads')
        .send({
          full_name: 'W5 Prod Lead',
          phone: '0905555555',
          channel: 'meta',
          client_id: '550e8400-e29b-41d4-a716-446655440000',
          source: 'api',
        })
        .expect(201);
      expect(res.body.id).toBeLessThan(900_000_000);
      expect(res.body.id).toBeGreaterThan(0);
    } finally {
      await prodApp.close();
      process.env.PTT_LEADS_CREATE_ID_MODE = prev ?? 'staging';
    }
  });

  it('POST /api/v1/leads returns 404 when write disabled', async () => {
    if (skip) return;
    const prev = process.env.PTT_LEADS_WRITE_ENABLED;
    process.env.PTT_LEADS_WRITE_ENABLED = '0';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    const disabledApp = moduleFixture.createNestApplication();
    await disabledApp.init();

    await request(disabledApp.getHttpServer()).post('/api/v1/leads').send({ full_name: 'X' }).expect(404);

    await disabledApp.close();
    process.env.PTT_LEADS_WRITE_ENABLED = prev ?? '1';
  });
});
