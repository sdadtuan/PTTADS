import type { FacebookHubClientRow } from './agency.types';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface FacebookHubDateWindow {
  dateFrom: string;
  dateTo: string;
  windowDays: number;
}

export interface FacebookHubCampaignExportRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  spend: number;
  leads_crm: number;
  cpl: number | null;
  target_cpl_vnd: number | null;
  hub_mapped: boolean;
}

export function normalizeHubClientUuid(raw: string | undefined): string | null {
  const text = String(raw ?? '').trim();
  if (!text || !UUID_RE.test(text)) return null;
  return text.toLowerCase();
}

export function parseHubDateYmd(raw: string | undefined, fallback: Date): Date {
  const text = String(raw ?? '').trim().slice(0, 10);
  if (!text) return fallback;
  const d = new Date(`${text}T00:00:00.000Z`);
  if (Number.isNaN(d.getTime())) return fallback;
  return d;
}

/** Resolve inclusive UTC date window (max 90 days). */
export function resolveFacebookHubDateWindow(input: {
  days?: number;
  dateTo?: string;
  dateFrom?: string;
}): FacebookHubDateWindow {
  const today = new Date();
  const defaultEnd = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  defaultEnd.setUTCDate(defaultEnd.getUTCDate() - 1);

  let end = parseHubDateYmd(input.dateTo, defaultEnd);
  let start: Date;

  const fromRaw = String(input.dateFrom ?? '').trim();
  if (fromRaw) {
    start = parseHubDateYmd(fromRaw, end);
    if (start.getTime() > end.getTime()) {
      const tmp = start;
      start = end;
      end = tmp;
    }
  } else {
    const days = Math.max(1, Math.min(Math.trunc(input.days ?? 7) || 7, 90));
    start = new Date(end);
    start.setUTCDate(start.getUTCDate() - (days - 1));
  }

  const maxSpanMs = 90 * 86400000;
  if (end.getTime() - start.getTime() > maxSpanMs) {
    start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 89);
  }

  const dateFrom = start.toISOString().slice(0, 10);
  const dateTo = end.toISOString().slice(0, 10);
  const windowDays =
    Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
  return { dateFrom, dateTo, windowDays };
}

function csvCell(value: unknown): string {
  const text = value == null ? '' : String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function buildFacebookHubClientsCsv(
  rows: FacebookHubClientRow[],
  meta: { dateFrom: string; dateTo: string },
): string {
  const header = [
    'client_id',
    'client_code',
    'client_name',
    'status',
    'spend_vnd',
    'leads_crm',
    'cpl_vnd',
    'campaigns',
    'unmapped_campaigns',
    'over_target_rows',
    'meta_has_token',
    'token_status',
    'date_from',
    'date_to',
  ];
  const lines = [header.join(',')];
  for (const row of rows) {
    lines.push(
      [
        row.id,
        row.code ?? '',
        row.name ?? '',
        row.status ?? '',
        row.spend,
        row.leads_crm,
        row.cpl ?? '',
        row.campaigns,
        row.unmapped_campaigns,
        row.over_target_rows,
        row.meta_has_token ? 'yes' : 'no',
        row.token_status,
        meta.dateFrom,
        meta.dateTo,
      ]
        .map(csvCell)
        .join(','),
    );
  }
  return `\uFEFF${lines.join('\n')}\n`;
}

export function buildFacebookHubCampaignsCsv(
  rows: FacebookHubCampaignExportRow[],
  meta: { dateFrom: string; dateTo: string },
): string {
  const header = [
    'client_id',
    'client_code',
    'client_name',
    'campaign_id',
    'campaign_name',
    'spend_vnd',
    'leads_crm',
    'cpl_vnd',
    'target_cpl_vnd',
    'hub_mapped',
    'date_from',
    'date_to',
  ];
  const lines = [header.join(',')];
  for (const row of rows) {
    lines.push(
      [
        row.client_id,
        row.client_code ?? '',
        row.client_name ?? '',
        row.external_campaign_id ?? '',
        row.external_campaign_name ?? '',
        row.spend,
        row.leads_crm,
        row.cpl ?? '',
        row.target_cpl_vnd ?? '',
        row.hub_mapped ? 'yes' : 'no',
        meta.dateFrom,
        meta.dateTo,
      ]
        .map(csvCell)
        .join(','),
    );
  }
  return `\uFEFF${lines.join('\n')}\n`;
}

export function facebookHubExportFilename(scope: string, dateFrom: string, dateTo: string): string {
  const safeScope = scope === 'campaigns' ? 'campaigns' : 'clients';
  return `meta-hub-${safeScope}-${dateFrom}_${dateTo}.csv`;
}
