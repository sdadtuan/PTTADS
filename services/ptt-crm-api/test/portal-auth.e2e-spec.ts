import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { pgReplicaReady } from './pg-contract-seed';

describe('Portal auth (Sprint 0 spike)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }
    process.env.PTT_PORTAL_JWT_SECRET = 'test-portal-secret-sprint0-min-len';
    process.env.PTT_PORTAL_STUB_USERS =
      'viewer@test.local:pass123:550e8400-e29b-41d4-a716-446655440000:viewer';
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

  it('POST /api/v1/portal/auth/login returns JWT', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email: 'viewer@test.local', password: 'pass123' })
      .expect(200);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.user.client_id).toBe('550e8400-e29b-41d4-a716-446655440000');
  });

  it('GET /api/v1/portal/auth/me with Bearer', async () => {
    if (!app) return;
    const login = await request(app.getHttpServer())
      .post('/api/v1/portal/auth/login')
      .send({ email: 'viewer@test.local', password: 'pass123' })
      .expect(200);
    await request(app.getHttpServer())
      .get('/api/v1/portal/auth/me')
      .set('Authorization', `Bearer ${login.body.access_token}`)
      .expect(200)
      .expect(({ body }) => {
        expect(body.client_id).toBe('550e8400-e29b-41d4-a716-446655440000');
        expect(body.role).toBe('viewer');
      });
  });
});
