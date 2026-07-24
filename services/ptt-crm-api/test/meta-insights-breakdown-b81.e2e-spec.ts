import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { E2E_CLIENT_ID, pgReplicaReady } from './pg-contract-seed';

describe('Meta insights breakdown B8.1', () => {
  let app: INestApplication;
  let staffToken = '';

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      return;
    }

    process.env.PTT_META_INSIGHTS_BREAKDOWN = '1';
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
    delete process.env.PTT_META_INSIGHTS_BREAKDOWN;
    if (app) {
      await app.close();
    }
  });

  it('GET /meta/insights/breakdown returns publisher_platform rows or disabled hint', async () => {
    if (!app || !staffToken) return;
    const res = await request(app.getHttpServer())
      .get(
        `/api/v1/meta/insights/breakdown?client_id=${E2E_CLIENT_ID}&type=publisher_platform&days=7`,
      )
      .set('Authorization', `Bearer ${staffToken}`)
      .expect(200);

    expect(res.body.ok).toBe(true);
    expect(res.body.breakdown_type).toBe('publisher_platform');
    expect(Array.isArray(res.body.rows)).toBe(true);
  });
});
