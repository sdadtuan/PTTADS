import { Pool } from 'pg';
import { loadGolden } from './contract-db';

const DATABASE_URL =
  process.env.DATABASE_URL ??
  process.env.PTT_DATABASE_URL ??
  'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency';

export const E2E_CLIENT_ID = '550e8400-e29b-41d4-a716-446655440000';

export async function ensureE2eTestClient(): Promise<void> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await pool.query(`DELETE FROM clients WHERE code = 'E2E_TEST' AND id <> $1::uuid`, [
      E2E_CLIENT_ID,
    ]);
    await pool.query(
      `INSERT INTO clients (id, code, name, status)
       VALUES ($1::uuid, 'E2E_TEST', 'E2E Test Client', 'active')
       ON CONFLICT (id) DO UPDATE SET
         code = EXCLUDED.code,
         name = EXCLUDED.name,
         status = EXCLUDED.status`,
      [E2E_CLIENT_ID],
    );
  } finally {
    await pool.end();
  }
}

export async function seedPgGoldenLead(): Promise<void> {
  const golden = loadGolden<Record<string, unknown>>('lead_v1.json');
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await ensureE2eTestClient();
    await pool.query(
      `INSERT INTO crm_leads (
         sqlite_lead_id, full_name, phone, email, status, source, owner_id,
         is_duplicate, meta_json, agency_client_id, channel, external_lead_id,
         campaign_id, received_at, created_at
       ) VALUES (
         $1, $2, $3, $4, $5, $6, $7,
         $8, '{}'::jsonb, $9::uuid, $10, $11,
         $12, $13::timestamptz, $14::timestamptz
       )
       ON CONFLICT (sqlite_lead_id) DO UPDATE SET
         full_name = EXCLUDED.full_name,
         phone = EXCLUDED.phone,
         email = EXCLUDED.email,
         status = EXCLUDED.status,
         source = EXCLUDED.source,
         owner_id = EXCLUDED.owner_id,
         is_duplicate = EXCLUDED.is_duplicate,
         agency_client_id = EXCLUDED.agency_client_id,
         channel = EXCLUDED.channel,
         external_lead_id = EXCLUDED.external_lead_id,
         campaign_id = EXCLUDED.campaign_id,
         received_at = EXCLUDED.received_at,
         created_at = EXCLUDED.created_at,
         synced_at = NOW()`,
      [
        golden.id,
        golden.full_name,
        golden.phone,
        golden.email,
        golden.status,
        golden.source,
        golden.owner_id,
        golden.is_duplicate,
        golden.client_id,
        golden.channel,
        golden.external_lead_id,
        golden.campaign_id,
        `${golden.received_at}T00:00:00Z`,
        `${golden.created_at}T00:00:00Z`,
      ],
    );
    await pool.query(
      `DELETE FROM crm_leads
       WHERE agency_client_id = $1::uuid
         AND sqlite_lead_id <> $2`,
      [golden.client_id ?? E2E_CLIENT_ID, golden.id],
    );
  } finally {
    await pool.end();
  }
}

export async function pgPerformanceTableReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'daily_performance'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function seedE2eDailyPerformance(): Promise<void> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await ensureE2eTestClient();
    const yesterday = new Date();
    yesterday.setUTCDate(yesterday.getUTCDate() - 1);
    const perfDate = yesterday.toISOString().slice(0, 10);
    await pool.query(
      `INSERT INTO daily_performance (
         client_id, channel, external_campaign_id, external_campaign_name,
         performance_date, spend, leads_crm, leads_platform, impressions, clicks
       ) VALUES (
         $1::uuid, 'meta', 'camp_e2e', 'E2E Campaign',
         $2::date, 150000, 3, 2, 1000, 50
       )
       ON CONFLICT (client_id, channel, external_campaign_id, performance_date) DO UPDATE SET
         external_campaign_name = EXCLUDED.external_campaign_name,
         spend = EXCLUDED.spend,
         leads_crm = EXCLUDED.leads_crm,
         leads_platform = EXCLUDED.leads_platform,
         impressions = EXCLUDED.impressions,
         clicks = EXCLUDED.clicks,
         synced_at = NOW()`,
      [E2E_CLIENT_ID, perfDate],
    );
  } finally {
    await pool.end();
  }
}

export async function pgCreativesTableReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'creative_submissions'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function seedE2eCreativePending(): Promise<string> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await ensureE2eTestClient();
    await pool.query(
      `DELETE FROM creative_submissions
       WHERE client_id = $1::uuid AND title = 'E2E Banner v1'`,
      [E2E_CLIENT_ID],
    );
    const result = await pool.query(
      `INSERT INTO creative_submissions (
         client_id, title, description, external_campaign_id, external_campaign_name,
         version, asset_url, status, submitted_by
       ) VALUES (
         $1::uuid, 'E2E Banner v1', 'Pending client approval', 'camp_e2e', 'E2E Campaign',
         1, 'https://example.com/creative-e2e.jpg', 'pending_client', 'am@test.local'
       )
       RETURNING id::text`,
      [E2E_CLIENT_ID],
    );
    return String(result.rows[0]?.id ?? '');
  } finally {
    await pool.end();
  }
}

export async function pgLaunchQaTableReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'launch_qa_runs'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function pgCampaignWritesTableReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'campaign_write_requests'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function pgReplicaReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'crm_leads'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function pgClientOffboardReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'client_offboard_audit'`,
    );
    if (Number(result.rows[0]?.c ?? 0) === 0) {
      return false;
    }
    const col = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'clients' AND column_name = 'tenant_locked'`,
    );
    return Number(col.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function resetE2eClientActive(): Promise<void> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await pool.query(
      `UPDATE clients
       SET status = 'active', tenant_locked = FALSE, updated_at = NOW()
       WHERE id = $1::uuid`,
      [E2E_CLIENT_ID],
    );
    await pool.query(`DELETE FROM client_offboard_audit WHERE client_id = $1::uuid`, [E2E_CLIENT_ID]);
  } finally {
    await pool.end();
  }
}
