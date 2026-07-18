import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { pgLaunchQaTableReady, pgReplicaReady } from './pg-contract-seed';

describe('Workflows API (T2/T3)', () => {
  let app: INestApplication;
  let launchQaReady = false;

  beforeAll(async () => {
    if (!(await pgReplicaReady())) return;
    launchQaReady = await pgLaunchQaTableReady();
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  it('POST onboarding/start returns workflow_id', async () => {
    if (!app) return;
    const res = await request(app.getHttpServer())
      .post('/api/v1/workflows/onboarding/start')
      .send({ client_id: '550e8400-e29b-41d4-a716-446655440000', started_by: 'am@test.local' })
      .expect(201);
    expect(res.body.ok).toBe(true);
    expect(res.body.workflow_id).toMatch(/^client-onboarding-/);
  });

  it('POST launch-qa/start creates run', async () => {
    if (!app || !launchQaReady) return;
    const res = await request(app.getHttpServer())
      .post('/api/v1/workflows/launch-qa/start')
      .send({
        client_id: '550e8400-e29b-41d4-a716-446655440000',
        external_campaign_id: 'camp_qa_e2e',
        started_by: 'am@test.local',
      })
      .expect(201);
    expect(res.body.ok).toBe(true);
    expect(res.body.run_id).toBeTruthy();
    expect(res.body.workflow_id).toMatch(/^launch-qa-/);
  });
});
