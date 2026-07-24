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

    const mapResult = await pool.query(
      `INSERT INTO hub_campaign_map (
         client_id, hub_campaign_id, channel, external_campaign_id,
         external_campaign_name, target_cpl_vnd, active
       ) VALUES (
         $1::uuid, 9000000001, 'meta', 'camp_e2e', 'E2E Campaign', 40000, TRUE
       )
       ON CONFLICT (client_id, channel, external_campaign_id) DO UPDATE SET
         external_campaign_name = EXCLUDED.external_campaign_name,
         target_cpl_vnd = EXCLUDED.target_cpl_vnd,
         active = EXCLUDED.active
       RETURNING id::text`,
      [E2E_CLIENT_ID],
    );
    const mapId = String(mapResult.rows[0]?.id ?? '');

    await pool.query(
      `INSERT INTO daily_performance (
         client_id, channel, external_campaign_id, external_campaign_name,
         performance_date, spend, leads_crm, leads_platform, impressions, clicks,
         hub_campaign_map_id
       ) VALUES (
         $1::uuid, 'meta', 'camp_e2e', 'E2E Campaign',
         $2::date, 150000, 3, 2, 1000, 50,
         NULLIF($3, '')::uuid
       )
       ON CONFLICT (client_id, channel, external_campaign_id, performance_date) DO UPDATE SET
         external_campaign_name = EXCLUDED.external_campaign_name,
         spend = EXCLUDED.spend,
         leads_crm = EXCLUDED.leads_crm,
         leads_platform = EXCLUDED.leads_platform,
         impressions = EXCLUDED.impressions,
         clicks = EXCLUDED.clicks,
         hub_campaign_map_id = EXCLUDED.hub_campaign_map_id,
         synced_at = NOW()`,
      [E2E_CLIENT_ID, perfDate, mapId],
    );
  } finally {
    await pool.end();
  }
}

export async function pgFacebookHubReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public'
         AND table_name IN ('clients', 'daily_performance', 'hub_campaign_map')`,
    );
    return Number(result.rows[0]?.c ?? 0) >= 3;
  } catch {
    return false;
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

export async function pgCapiEventLogReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'capi_event_log'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function seedE2eMetaChannelAccount(): Promise<string> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await ensureE2eTestClient();
    const result = await pool.query(
      `INSERT INTO client_channel_accounts (
         client_id, channel, external_account_id, display_name, status, meta
       ) VALUES (
         $1::uuid, 'meta', 'act_e2e_meta', 'E2E Meta Account', 'active',
         '{"pixel_id":"999888777","capi_enabled":true}'::jsonb
       )
       ON CONFLICT (client_id, channel, external_account_id) DO UPDATE SET
         display_name = EXCLUDED.display_name,
         status = EXCLUDED.status,
         meta = EXCLUDED.meta,
         updated_at = NOW()
       RETURNING id::text`,
      [E2E_CLIENT_ID],
    );
    return String(result.rows[0]?.id ?? '');
  } finally {
    await pool.end();
  }
}

export async function pgMetaConversionRulesReady(): Promise<boolean> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    const result = await pool.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'meta_conversion_rules'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  } catch {
    return false;
  } finally {
    await pool.end();
  }
}

export async function seedE2eConversionRules(): Promise<string> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await ensureE2eTestClient();
    const result = await pool.query(
      `INSERT INTO meta_conversion_rules (
         client_id, lead_status, event_name, enabled, notes
       ) VALUES (
         $1::uuid, 'e2e_qualified', 'CompleteRegistration', TRUE, 'e2e client rule'
       )
       ON CONFLICT DO NOTHING
       RETURNING id::text`,
      [E2E_CLIENT_ID],
    );
    if (result.rows[0]?.id) {
      return String(result.rows[0].id);
    }
    const existing = await pool.query(
      `SELECT id::text FROM meta_conversion_rules
       WHERE client_id = $1::uuid AND lead_status = 'e2e_qualified'
       LIMIT 1`,
      [E2E_CLIENT_ID],
    );
    return String(existing.rows[0]?.id ?? '');
  } finally {
    await pool.end();
  }
}

export async function seedE2eFailedCapiEventLog(): Promise<string> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await ensureE2eTestClient();
    const result = await pool.query(
      `INSERT INTO capi_event_log (
         client_id, event_name, event_id, lead_id, pixel_id,
         payload_hash, status, error_message
       ) VALUES (
         $1::uuid, 'Lead', 'leadgen_e2e_failed_1', 1001, '999888777',
         'e2ehashfailed1', 'failed', 'graph timeout'
       )
       ON CONFLICT (client_id, event_id, event_name) DO UPDATE SET
         status = 'failed',
         error_message = EXCLUDED.error_message
       RETURNING id::text`,
      [E2E_CLIENT_ID],
    );
    return String(result.rows[0]?.id ?? '');
  } finally {
    await pool.end();
  }
}

export async function seedE2eCapiEventLog(): Promise<void> {
  const pool = new Pool({ connectionString: DATABASE_URL });
  try {
    await ensureE2eTestClient();
    await pool.query(
      `INSERT INTO capi_event_log (
         client_id, event_name, event_id, lead_id, pixel_id,
         payload_hash, status, sent_at
       ) VALUES (
         $1::uuid, 'Lead', 'leadgen_e2e_test_1', 1001, '999888777',
         'e2ehashlead1', 'sent', NOW()
       )
       ON CONFLICT (client_id, event_id, event_name) DO UPDATE SET
         status = EXCLUDED.status,
         sent_at = EXCLUDED.sent_at`,
      [E2E_CLIENT_ID],
    );
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
