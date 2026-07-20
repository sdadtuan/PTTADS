import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { pgReplicaReady } from './pg-contract-seed';

describe('Staff auth (Phase 0)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }
    process.env.PTT_STAFF_JWT_SECRET = 'test-staff-secret-phase0-min-len-32';
    process.env.PTT_STAFF_STUB_USERS =
      'staff@test.local:pass123:staff-001:1:Test Staff';
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';

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

  it('POST /api/v1/staff/auth/login returns JWT pair', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer())
      .post('/api/v1/staff/auth/login')
      .send({ email: 'staff@test.local', password: 'pass123' })
      .expect(200);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.refresh_token).toBeTruthy();
    expect(res.body.user.display_name).toBe('Test Staff');
  });

  it('GET /api/v1/staff/auth/me returns caps', async () => {
    if (!app) return;
    const login = await request(app.getHttpServer())
      .post('/api/v1/staff/auth/login')
      .send({ email: 'staff@test.local', password: 'pass123' })
      .expect(200);
    await request(app.getHttpServer())
      .get('/api/v1/staff/auth/me')
      .set('Authorization', `Bearer ${login.body.access_token}`)
      .expect(200)
      .expect(({ body }) => {
        expect(body.email).toBe('staff@test.local');
        expect(Array.isArray(body.caps)).toBe(true);
        expect(body.caps.some((c: { section: string }) => c.section === 'crm_leads')).toBe(true);
      });
  });

  it('POST /api/v1/staff/auth/refresh rotates tokens', async () => {
    if (!app) return;
    const login = await request(app.getHttpServer())
      .post('/api/v1/staff/auth/login')
      .send({ email: 'staff@test.local', password: 'pass123' })
      .expect(200);
    const refreshed = await request(app.getHttpServer())
      .post('/api/v1/staff/auth/refresh')
      .send({ refresh_token: login.body.refresh_token })
      .expect(200);
    expect(refreshed.body.access_token).toBeTruthy();
    expect(refreshed.body.access_token).not.toBe(login.body.access_token);
  });
});
