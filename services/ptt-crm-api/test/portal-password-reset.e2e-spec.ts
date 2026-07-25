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

describe('Portal password reset (GAP-P0-02)', () => {
  let app: INestApplication;
  let tablesReady = false;

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';
    process.env.PTT_PORTAL_JWT_SECRET = 'test-portal-secret-sprint0-min-len';
    process.env.PTT_PORTAL_PUBLIC_URL = 'http://127.0.0.1:3100';

    const pool = new Pool({ connectionString: DATABASE_URL });
    try {
      const check = await pool.query(
        `SELECT 1 FROM information_schema.tables WHERE table_name = 'portal_password_reset_tokens'`,
      );
      tablesReady = (check.rowCount ?? 0) > 0;
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

  it('POST forgot-password always returns ok for unknown email', async () => {
    if (!app) return;
    await request(app.getHttpServer())
      .post('/api/v1/portal/auth/forgot-password')
      .send({ email: 'nobody-here@test.local' })
      .expect(200)
      .expect(({ body }) => {
        expect(body.ok).toBe(true);
        expect(body.message).toBeTruthy();
      });
  });

  it('full reset flow when tables ready', async () => {
    if (!app || !tablesReady) return;

    const email = `reset-e2e-${Date.now()}@test.local`;
    const create = await request(app.getHttpServer())
      .post(`/api/v1/clients/${E2E_CLIENT_ID}/portal-users`)
      .send({ email, role: 'viewer', password: 'oldpassword12' })
      .expect(201);

    const forgot = await request(app.getHttpServer())
      .post('/api/v1/portal/auth/forgot-password')
      .send({ email })
      .expect(200);

    expect(forgot.body.reset_url).toBeTruthy();
    const url = new URL(forgot.body.reset_url as string);
    const token = url.searchParams.get('token');
    expect(token).toBeTruthy();

    await request(app.getHttpServer())
      .get('/api/v1/portal/auth/reset-password/validate')
      .query({ token })
      .expect(200)
      .expect(({ body }) => {
        expect(body.ok).toBe(true);
        expect(body.email_masked).toContain('@');
      });

    await request(app.getHttpServer())
      .post('/api/v1/portal/auth/reset-password')
      .send({ token, password: 'newpassword99' })
      .expect(200)
      .expect(({ body }) => {
        expect(body.ok).toBe(true);
      });

    await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email, password: 'newpassword99' })
      .expect(200);

    await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email, password: 'oldpassword12' })
      .expect(401);
  });
});
