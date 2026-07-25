import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { Pool } from 'pg';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { E2E_CLIENT_ID, pgReplicaReady } from './pg-contract-seed';

const DATABASE_URL =
  process.env.DATABASE_URL ??
  process.env.PTT_DATABASE_URL ??
  'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency';

describe('Portal client users (GAP-P0-01)', () => {
  let app: INestApplication;
  let tableReady = false;

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';
    process.env.PTT_PORTAL_JWT_SECRET = 'test-portal-secret-sprint0-min-len';

    const pool = new Pool({ connectionString: DATABASE_URL });
    try {
      const check = await pool.query(
        `SELECT 1 FROM information_schema.tables WHERE table_name = 'portal_client_users'`,
      );
      tableReady = (check.rowCount ?? 0) > 0;
    } finally {
      await pool.end();
    }

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

  it('GET portal-users lists users for client', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer()).get(`/api/v1/clients/${E2E_CLIENT_ID}/portal-users`).expect(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.client_id).toBe(E2E_CLIENT_ID);
    expect(Array.isArray(res.body.users)).toBe(true);
    if (tableReady) {
      expect(res.body.table_ready).toBe(true);
    }
  });

  it('POST portal-users creates user and login works', async () => {
    if (!app || !tableReady) return;
    const email = `portal-e2e-${Date.now()}@test.local`;
    const create = await request(app.getHttpServer())
      .post(`/api/v1/clients/${E2E_CLIENT_ID}/portal-users`)
      .send({ email, role: 'approver' })
      .expect(201);
    expect(create.body.ok).toBe(true);
    expect(create.body.user.email).toBe(email);
    expect(create.body.temporary_password).toBeTruthy();

    await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email, password: create.body.temporary_password })
      .expect(200)
      .expect(({ body }) => {
        expect(body.user.client_id).toBe(E2E_CLIENT_ID);
        expect(body.user.role).toBe('approver');
      });

    const userId = create.body.user.id as string;
    await request(app.getHttpServer())
      .patch(`/api/v1/clients/${E2E_CLIENT_ID}/portal-users/${userId}`)
      .send({ active: false })
      .expect(200)
      .expect(({ body }) => {
        expect(body.active).toBe(false);
      });
  });
});
