import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { createContractDatabase, loadGolden, removeDatabase } from './contract-db';

describe('Leads API v1 (e2e contract)', () => {
  let app: INestApplication;
  let dbPath: string;

  beforeAll(async () => {
    dbPath = createContractDatabase();
    process.env.PTT_SQLITE_PATH = dbPath;
    process.env.PTT_LEADS_READ_SOURCE = 'sqlite';
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';
    process.env.PORT = '0';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
    removeDatabase(dbPath);
  });

  it('GET /health', () => {
    return request(app.getHttpServer())
      .get('/health')
      .expect(200)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body.ok).toBe(true);
        expect(body.service).toBe('ptt-crm-api');
        expect(body.leads_read_source).toBe('sqlite');
        expect(body.sqlite).toBe(true);
      });
  });

  it('GET /api/v1/leads/:id matches golden lead_v1.json', () => {
    const golden = loadGolden<Record<string, unknown>>('lead_v1.json');
    return request(app.getHttpServer())
      .get('/api/v1/leads/1')
      .expect(200)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body).toEqual(golden);
      });
  });

  it('GET /api/v1/leads matches golden list_leads_response.json', () => {
    const golden = loadGolden<Record<string, unknown>>('list_leads_response.json');
    return request(app.getHttpServer())
      .get('/api/v1/leads?limit=50&offset=0')
      .expect(200)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body).toEqual(golden);
      });
  });

  it('GET /api/v1/leads/:id 404 matches golden not_found.json', () => {
    const golden = loadGolden<Record<string, unknown>>('not_found.json');
    return request(app.getHttpServer())
      .get('/api/v1/leads/999')
      .expect(404)
      .expect(({ body }: { body: Record<string, unknown> }) => {
        expect(body).toEqual(golden);
      });
  });
});
