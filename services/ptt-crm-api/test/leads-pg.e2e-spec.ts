import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { loadGolden } from './contract-db';
import { pgReplicaReady, seedPgGoldenLead } from './pg-contract-seed';

describe('Leads API v1 PG read (e2e contract)', () => {
  let app: INestApplication;
  let skip = false;

  beforeAll(async () => {
    if (!(await pgReplicaReady())) {
      skip = true;
      return;
    }
    await seedPgGoldenLead();
    process.env.PTT_LEADS_READ_SOURCE = 'pg';
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';
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

  it('GET /health reports pg read source', async () => {
    if (skip) {
      return;
    }
    await request(app.getHttpServer())
      .get('/health')
      .expect(200)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body.leads_read_source).toBe('pg');
      });
  });

  it('GET /api/v1/leads/:id matches golden from PG replica', async () => {
    if (skip) {
      return;
    }
    const golden = loadGolden<Record<string, unknown>>('lead_v1.json');
    await request(app.getHttpServer())
      .get('/api/v1/leads/1')
      .expect(200)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body).toEqual(golden);
      });
  });

  it('GET /api/v1/leads matches golden list from PG replica', async () => {
    if (skip) {
      return;
    }
    const golden = loadGolden<Record<string, unknown>>('list_leads_response.json');
    const clientId = (golden.leads as Array<{ client_id: string }>)[0].client_id;
    await request(app.getHttpServer())
      .get(`/api/v1/leads?client_id=${clientId}&status=new&limit=50&offset=0`)
      .expect(200)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body).toEqual(golden);
      });
  });
});
