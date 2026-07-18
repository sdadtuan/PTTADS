import { LeadRow, LeadV1, PgLeadRow } from './leads.types';
import { formatLeadTs } from './lead-ts.format';

function parseMeta(raw: string | null | undefined): Record<string, unknown> {
  if (!raw) {
    return {};
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function metaString(meta: Record<string, unknown>, key: string): string {
  const val = meta[key];
  if (val === undefined || val === null) {
    return '';
  }
  return String(val);
}

/** Mirror ptt_crm/leads_read.py lead_row_to_v1() — contract frozen Step 2. */
export function leadRowToV1(row: LeadRow): LeadV1 {
  const meta = parseMeta(row.meta_json);
  const channel = String(
    metaString(meta, 'channel') ||
      metaString(meta, 'ingest_channel') ||
      metaString(meta, 'utm_source') ||
      row.source ||
      '',
  );
  const campaignRaw = String(
    metaString(meta, 'campaign_id') ||
      metaString(meta, 'facebook_campaign_id') ||
      metaString(meta, 'zalo_campaign_id') ||
      '',
  );
  const externalRaw = String(
    metaString(meta, 'facebook_leadgen_id') ||
      metaString(meta, 'zalo_lead_id') ||
      metaString(meta, 'external_lead_id') ||
      '',
  );
  const agencyClientId = meta.agency_client_id;
  const receivedAt = String(
    metaString(meta, 'ingested_at') ||
      metaString(meta, 'facebook_created_time') ||
      row.created_at ||
      '',
  );

  return {
    id: Number(row.id),
    full_name: row.full_name ?? '',
    phone: row.phone ?? '',
    email: row.email ?? '',
    status: row.status ?? '',
    source: row.source ?? '',
    channel,
    client_id:
      agencyClientId !== undefined && agencyClientId !== null ? String(agencyClientId) : null,
    campaign_id: campaignRaw || null,
    external_lead_id: externalRaw || null,
    owner_id: row.owner_id != null ? Number(row.owner_id) : null,
    created_at: row.created_at ?? '',
    received_at: receivedAt,
    is_duplicate: Boolean(row.is_duplicate),
  };
}

/** Map PG crm_leads read replica row → LeadV1 (Bước 7). */
export function pgRowToV1(row: PgLeadRow): LeadV1 {
  return {
    id: Number(row.sqlite_lead_id),
    full_name: row.full_name ?? '',
    phone: row.phone ?? '',
    email: row.email ?? '',
    status: row.status ?? '',
    source: row.source ?? '',
    channel: row.channel ?? '',
    client_id: row.agency_client_id ? String(row.agency_client_id) : null,
    campaign_id: row.campaign_id || null,
    external_lead_id: row.external_lead_id || null,
    owner_id: row.owner_id != null ? Number(row.owner_id) : null,
    created_at: formatLeadTs(row.created_at),
    received_at: formatLeadTs(row.received_at),
    is_duplicate: Boolean(row.is_duplicate),
  };
}
