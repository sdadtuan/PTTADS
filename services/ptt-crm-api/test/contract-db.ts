import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { DatabaseSync } from 'node:sqlite';

const CLIENT_ID = '550e8400-e29b-41d4-a716-446655440000';

export function createContractDatabase(): string {
  const dbPath = path.join(os.tmpdir(), `ptt-crm-api-contract-${Date.now()}.db`);
  const db = new DatabaseSync(dbPath);
  db.exec(`
    CREATE TABLE crm_leads (
      id INTEGER PRIMARY KEY,
      full_name TEXT, phone TEXT, email TEXT,
      status TEXT, source TEXT, owner_id INTEGER,
      created_at TEXT, is_duplicate INTEGER DEFAULT 0,
      meta_json TEXT NOT NULL DEFAULT '{}'
    )
  `);
  db.prepare(
    `INSERT INTO crm_leads (full_name, phone, status, source, created_at, meta_json)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(
    'Lead A',
    '0901111111',
    'new',
    'facebook',
    '2026-07-17',
    JSON.stringify({
      agency_client_id: CLIENT_ID,
      channel: 'meta',
      facebook_leadgen_id: 'fb-1',
    }),
  );
  db.close();
  return dbPath;
}

export function loadGolden<T>(name: string): T {
  const fixturePath = path.resolve(
    __dirname,
    '..',
    '..',
    '..',
    'tests',
    'fixtures',
    'api',
    'leads-v1',
    name,
  );
  return JSON.parse(fs.readFileSync(fixturePath, 'utf-8')) as T;
}

export function removeDatabase(dbPath: string): void {
  try {
    fs.unlinkSync(dbPath);
  } catch {
    // ignore
  }
}
