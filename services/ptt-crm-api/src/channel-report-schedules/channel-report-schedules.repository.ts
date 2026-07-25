import {
  BadRequestException,
  Injectable,
  NotFoundException,
  OnModuleDestroy,
} from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  ChannelReportCadence,
  ChannelReportFormat,
  ChannelReportKind,
  ChannelReportScheduleRow,
  ChannelReportScope,
} from './channel-report-schedules.types';

function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function parseEmails(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map(String).filter(Boolean);
  try {
    const data = JSON.parse(String(raw ?? '[]'));
    return Array.isArray(data) ? data.map(String).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function tableNames(kind: ChannelReportKind): { schedule: string; runs: string } {
  return kind === 'meta'
    ? { schedule: 'meta_report_schedules', runs: 'meta_report_schedule_runs' }
    : { schedule: 'zalo_report_schedules', runs: 'zalo_report_schedule_runs' };
}

@Injectable()
export class ChannelReportSchedulesRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async tableReady(kind: ChannelReportKind): Promise<boolean> {
    const { schedule } = tableNames(kind);
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = $1`,
        [schedule],
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  computeNextRun(
    cadence: ChannelReportCadence,
    dayOfWeek: number,
    dayOfMonth: number,
    fromDate = new Date(),
  ): string {
    const today = new Date(fromDate);
    today.setHours(0, 0, 0, 0);
    if (cadence === 'monthly') {
      const dom = Math.max(1, Math.min(28, dayOfMonth || 1));
      let candidate = new Date(today.getFullYear(), today.getMonth(), dom);
      if (candidate <= today) {
        candidate = new Date(today.getFullYear(), today.getMonth() + 1, dom);
      }
      return candidate.toISOString().slice(0, 10);
    }
    const dow = (dayOfWeek || 0) % 7;
    const currentDow = (today.getDay() + 6) % 7;
    let daysAhead = (dow - currentDow + 7) % 7;
    if (daysAhead === 0) daysAhead = 7;
    const next = new Date(today);
    next.setDate(today.getDate() + daysAhead);
    return next.toISOString().slice(0, 10);
  }

  private mapRow(r: Record<string, unknown>): ChannelReportScheduleRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      report_scope: (r.report_scope === 'campaigns' ? 'campaigns' : 'clients') as ChannelReportScope,
      export_format: (r.export_format === 'csv' ? 'csv' : 'pdf') as ChannelReportFormat,
      window_days: Number(r.window_days ?? 7),
      cadence: (r.cadence === 'monthly' ? 'monthly' : 'weekly') as ChannelReportCadence,
      day_of_week: Number(r.day_of_week ?? 0),
      day_of_month: Number(r.day_of_month ?? 1),
      recipient_emails: parseEmails(r.recipient_emails_json),
      cc_emails: parseEmails(r.cc_emails_json),
      bcc_emails: parseEmails(r.bcc_emails_json),
      portal_link_enabled: r.portal_link_enabled !== false,
      active: r.active === true || r.active === 't' || r.active === 1,
      next_run_at: r.next_run_at ? String(r.next_run_at).slice(0, 10) : null,
      last_sent_at: iso(r.last_sent_at),
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
    };
  }

  async list(params: {
    kind: ChannelReportKind;
    clientId: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: ChannelReportScheduleRow[]; total: number; limit: number; offset: number }> {
    const { schedule } = tableNames(params.kind);
    const limit = Math.min(100, Math.max(1, Number(params.limit) || 50));
    const offset = Math.max(0, Number(params.offset) || 0);
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${schedule} WHERE client_id = $1::uuid`,
      [params.clientId],
    );
    const result = await this.db.query(
      `SELECT rs.*, cl.name AS client_name
       FROM ${schedule} rs
       JOIN clients cl ON cl.id = rs.client_id
       WHERE rs.client_id = $1::uuid
       ORDER BY rs.created_at DESC
       LIMIT $2 OFFSET $3`,
      [params.clientId, limit, offset],
    );
    return {
      items: result.rows.map((r) => this.mapRow(r as Record<string, unknown>)),
      total: Number(count.rows[0]?.c ?? 0),
      limit,
      offset,
    };
  }

  async get(kind: ChannelReportKind, id: string): Promise<ChannelReportScheduleRow | null> {
    const { schedule } = tableNames(kind);
    const result = await this.db.query(
      `SELECT rs.*, cl.name AS client_name
       FROM ${schedule} rs
       JOIN clients cl ON cl.id = rs.client_id
       WHERE rs.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    return this.mapRow(result.rows[0] as Record<string, unknown>);
  }

  async create(params: {
    kind: ChannelReportKind;
    clientId: string;
    reportScope?: ChannelReportScope;
    exportFormat?: ChannelReportFormat;
    windowDays?: number;
    cadence?: ChannelReportCadence;
    dayOfWeek?: number;
    dayOfMonth?: number;
    recipientEmails?: string[];
    ccEmails?: string[];
    bccEmails?: string[];
    portalLinkEnabled?: boolean;
  }): Promise<ChannelReportScheduleRow> {
    const { schedule } = tableNames(params.kind);
    const cadence = params.cadence ?? 'weekly';
    if (!['weekly', 'monthly'].includes(cadence)) {
      throw new BadRequestException({ error: 'invalid_cadence' });
    }
    const reportScope = params.reportScope ?? 'clients';
    const exportFormat = params.exportFormat ?? 'pdf';
    if (exportFormat === 'pdf' && reportScope === 'campaigns' && params.kind === 'zalo') {
      throw new BadRequestException({ error: 'zalo_pdf_campaigns_not_supported' });
    }
    const windowDays = Math.min(90, Math.max(1, Number(params.windowDays) || 7));
    const nextRun = this.computeNextRun(cadence, params.dayOfWeek ?? 0, params.dayOfMonth ?? 1);
    const result = await this.db.query(
      `INSERT INTO ${schedule} (
         client_id, report_scope, export_format, window_days, cadence,
         day_of_week, day_of_month, recipient_emails_json, cc_emails_json, bcc_emails_json,
         portal_link_enabled, next_run_at
       ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10::jsonb, $11, $12::date)
       RETURNING id`,
      [
        params.clientId,
        reportScope,
        exportFormat,
        windowDays,
        cadence,
        params.dayOfWeek ?? 0,
        params.dayOfMonth ?? 1,
        JSON.stringify(params.recipientEmails ?? []),
        JSON.stringify(params.ccEmails ?? []),
        JSON.stringify(params.bccEmails ?? []),
        params.portalLinkEnabled !== false,
        nextRun,
      ],
    );
    const id = String(result.rows[0]?.id ?? '');
    const row = await this.get(params.kind, id);
    if (!row) throw new NotFoundException({ error: 'schedule_not_found' });
    return row;
  }

  async update(
    kind: ChannelReportKind,
    id: string,
    patch: Record<string, unknown>,
  ): Promise<ChannelReportScheduleRow> {
    const existing = await this.get(kind, id);
    if (!existing) throw new NotFoundException({ error: 'schedule_not_found' });
    const { schedule } = tableNames(kind);

    const cadence = (patch.cadence as ChannelReportCadence | undefined) ?? existing.cadence;
    const dayOfWeek =
      patch.day_of_week != null ? Number(patch.day_of_week) : existing.day_of_week;
    const dayOfMonth =
      patch.day_of_month != null ? Number(patch.day_of_month) : existing.day_of_month;

    const sets: string[] = ['updated_at = NOW()'];
    const values: unknown[] = [id];
    let idx = 2;

    const assign = (col: string, val: unknown) => {
      sets.push(`${col} = $${idx++}`);
      values.push(val);
    };

    if (patch.report_scope != null) assign('report_scope', patch.report_scope);
    if (patch.export_format != null) assign('export_format', patch.export_format);
    if (patch.window_days != null) assign('window_days', Math.min(90, Math.max(1, Number(patch.window_days) || 7)));
    if (patch.cadence != null) assign('cadence', patch.cadence);
    if (patch.day_of_week != null) assign('day_of_week', dayOfWeek);
    if (patch.day_of_month != null) assign('day_of_month', dayOfMonth);
    if (patch.recipient_emails != null) assign('recipient_emails_json', JSON.stringify(patch.recipient_emails));
    if (patch.cc_emails != null) assign('cc_emails_json', JSON.stringify(patch.cc_emails));
    if (patch.bcc_emails != null) assign('bcc_emails_json', JSON.stringify(patch.bcc_emails));
    if (patch.portal_link_enabled != null) assign('portal_link_enabled', Boolean(patch.portal_link_enabled));
    if (patch.active != null) assign('active', Boolean(patch.active));

    if (
      patch.cadence != null ||
      patch.day_of_week != null ||
      patch.day_of_month != null ||
      patch.active === true
    ) {
      assign('next_run_at', this.computeNextRun(cadence, dayOfWeek, dayOfMonth));
    }

    await this.db.query(`UPDATE ${schedule} SET ${sets.join(', ')} WHERE id = $1::uuid`, values);
    const updated = await this.get(kind, id);
    if (!updated) throw new NotFoundException({ error: 'schedule_not_found' });
    return updated;
  }

  async delete(kind: ChannelReportKind, id: string): Promise<{ ok: boolean }> {
    const { schedule } = tableNames(kind);
    const existing = await this.get(kind, id);
    if (!existing) throw new NotFoundException({ error: 'schedule_not_found' });
    await this.db.query(`DELETE FROM ${schedule} WHERE id = $1::uuid`, [id]);
    return { ok: true };
  }
}
