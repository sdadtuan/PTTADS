import {
  BadRequestException,
  Injectable,
  NotFoundException,
  OnModuleDestroy,
} from '@nestjs/common';
import { promises as dns } from 'dns';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { revenueAttributedQuery } from './email-marketing-attribution.util';
import {
  EmailDeliverabilityDomainRow,
  EmailDeliverabilityReport,
  EmailEngagementSeriesPoint,
  EmailJourneyRow,
  EmailJourneyStepRow,
  EmailListResponse,
  EmailReportScheduleRow,
  EmailReportsCampaignStats,
  EmailReportsSummary,
} from './email-marketing.types';
import { clampLimit, clampOffset, iso } from './email-marketing.util';

const SCHEMA = 'email_mkt';

type GraphNode = { id: string; type: string; config?: Record<string, unknown> };

@Injectable()
export class EmailMarketingEnterpriseRepository implements OnModuleDestroy {
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

  static pagination(limit?: number, offset?: number) {
    return { limit: clampLimit(limit), offset: clampOffset(offset) };
  }

  private async audit(params: {
    clientId: string;
    actor: string;
    action: string;
    entityType: string;
    entityId: string;
    after?: Record<string, unknown>;
  }): Promise<void> {
    await this.db.query(
      `INSERT INTO ${SCHEMA}.audit_log (client_id, actor, action, entity_type, entity_id, after_json)
       VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6::jsonb)`,
      [
        params.clientId,
        params.actor,
        params.action,
        params.entityType,
        params.entityId,
        JSON.stringify(params.after ?? {}),
      ],
    );
  }

  async listJourneys(params: {
    clientId?: string;
    status?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailJourneyRow>> {
    const values: unknown[] = [];
    const clauses: string[] = ['1=1'];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`j.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.status) {
      clauses.push(`j.status = $${idx++}`);
      values.push(params.status);
    }
    const where = clauses.join(' AND ');
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.journeys j WHERE ${where}`,
      values,
    );
    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT j.id, j.client_id, cl.name AS client_name, j.name, j.trigger_type,
              j.graph_json, j.entry_segment_id, seg.name AS entry_segment_name,
              j.status, j.enrolled_count, j.created_by, j.created_at, j.updated_at
       FROM ${SCHEMA}.journeys j
       JOIN clients cl ON cl.id = j.client_id
       LEFT JOIN ${SCHEMA}.segments seg ON seg.id = j.entry_segment_id
       WHERE ${where}
       ORDER BY j.updated_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );
    return {
      ok: true,
      items: result.rows.map((r) => this.mapJourney(r)),
      total: Number(count.rows[0]?.c ?? 0),
      limit: params.limit,
      offset: params.offset,
    };
  }

  async getJourney(id: string): Promise<EmailJourneyRow | null> {
    const result = await this.db.query(
      `SELECT j.id, j.client_id, cl.name AS client_name, j.name, j.trigger_type,
              j.graph_json, j.entry_segment_id, seg.name AS entry_segment_name,
              j.status, j.enrolled_count, j.created_by, j.created_at, j.updated_at
       FROM ${SCHEMA}.journeys j
       JOIN clients cl ON cl.id = j.client_id
       LEFT JOIN ${SCHEMA}.segments seg ON seg.id = j.entry_segment_id
       WHERE j.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    const journey = this.mapJourney(result.rows[0]);
    const steps = await this.db.query(
      `SELECT id, journey_id, step_key, step_type, config_json, sort_order, created_at
       FROM ${SCHEMA}.journey_steps WHERE journey_id = $1::uuid ORDER BY sort_order ASC`,
      [id],
    );
    journey.steps = steps.rows.map((s) => this.mapJourneyStep(s));
    return journey;
  }

  async createJourney(params: {
    clientId: string;
    name: string;
    triggerType?: string;
    entrySegmentId?: string;
    graphJson?: Record<string, unknown>;
    actor: string;
  }): Promise<EmailJourneyRow> {
    const graph = params.graphJson ?? this.defaultGraph(params.entrySegmentId);
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.journeys (
         client_id, name, trigger_type, graph_json, entry_segment_id, created_by, status
       ) VALUES ($1::uuid, $2, $3, $4::jsonb, $5::uuid, $6, 'draft')
       RETURNING id::text`,
      [
        params.clientId,
        params.name.trim(),
        params.triggerType?.trim() || 'segment_enter',
        JSON.stringify(graph),
        params.entrySegmentId ?? null,
        params.actor,
      ],
    );
    const id = String(result.rows[0].id);
    await this.syncJourneySteps(id, graph);
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'journey_created',
      entityType: 'journey',
      entityId: id,
    });
    const row = await this.getJourney(id);
    if (!row) throw new NotFoundException({ error: 'journey_not_found' });
    return row;
  }

  async updateJourney(
    id: string,
    patch: {
      name?: string;
      graph_json?: Record<string, unknown>;
      entry_segment_id?: string | null;
      status?: string;
    },
    actor: string,
  ): Promise<EmailJourneyRow> {
    const existing = await this.getJourney(id);
    if (!existing) throw new NotFoundException({ error: 'journey_not_found' });
    const fields: string[] = [];
    const values: unknown[] = [];
    let idx = 1;
    if (patch.name != null) {
      fields.push(`name = $${idx++}`);
      values.push(patch.name.trim());
    }
    if (patch.graph_json != null) {
      fields.push(`graph_json = $${idx++}::jsonb`);
      values.push(JSON.stringify(patch.graph_json));
    }
    if (patch.entry_segment_id !== undefined) {
      fields.push(`entry_segment_id = $${idx++}::uuid`);
      values.push(patch.entry_segment_id);
    }
    if (patch.status != null) {
      fields.push(`status = $${idx++}`);
      values.push(patch.status);
    }
    if (fields.length === 0) return existing;
    fields.push('updated_at = NOW()');
    values.push(id);
    await this.db.query(
      `UPDATE ${SCHEMA}.journeys SET ${fields.join(', ')} WHERE id = $${idx}::uuid`,
      values,
    );
    if (patch.graph_json != null) {
      await this.syncJourneySteps(id, patch.graph_json);
    }
    await this.audit({
      clientId: existing.client_id,
      actor,
      action: 'journey_updated',
      entityType: 'journey',
      entityId: id,
      after: patch as Record<string, unknown>,
    });
    const row = await this.getJourney(id);
    if (!row) throw new NotFoundException({ error: 'journey_not_found' });
    return row;
  }

  async activateJourney(id: string, actor: string): Promise<EmailJourneyRow> {
    const journey = await this.getJourney(id);
    if (!journey) throw new NotFoundException({ error: 'journey_not_found' });
    if (journey.status !== 'draft' && journey.status !== 'paused') {
      throw new BadRequestException({ error: 'invalid_status', status: journey.status });
    }
    const nodes = (journey.graph_json?.nodes ?? []) as GraphNode[];
    const hasSend = nodes.some((n) => n.type === 'send');
    if (!hasSend) {
      throw new BadRequestException({ error: 'journey_missing_send_step' });
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.journeys SET status = 'active', updated_at = NOW() WHERE id = $1::uuid`,
      [id],
    );
    await this.audit({
      clientId: journey.client_id,
      actor,
      action: 'journey_activated',
      entityType: 'journey',
      entityId: id,
    });
    const row = await this.getJourney(id);
    if (!row) throw new NotFoundException({ error: 'journey_not_found' });
    return row;
  }

  async listDomains(params: {
    clientId?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailDeliverabilityDomainRow>> {
    const values: unknown[] = [];
    let filter = '';
    if (params.clientId) {
      values.push(params.clientId);
      filter = ` WHERE d.client_id = $1::uuid`;
    }
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.domains d${filter}`,
      values,
    );
    values.push(params.limit, params.offset);
    const idx = values.length - 1;
    const result = await this.db.query(
      `SELECT d.id, d.client_id, cl.name AS client_name, d.domain,
              d.spf_status, d.dkim_status, d.dmarc_status, d.last_checked_at,
              d.warm_up_stage, d.daily_volume_cap, d.status, d.created_at
       FROM ${SCHEMA}.domains d
       JOIN clients cl ON cl.id = d.client_id
       ${filter}
       ORDER BY d.created_at DESC
       LIMIT $${idx} OFFSET $${idx + 1}`,
      values,
    );
    return {
      ok: true,
      items: result.rows.map((r) => this.mapDomain(r)),
      total: Number(count.rows[0]?.c ?? 0),
      limit: params.limit,
      offset: params.offset,
    };
  }

  async registerDomain(params: {
    clientId: string;
    domain: string;
    actor: string;
  }): Promise<EmailDeliverabilityDomainRow> {
    const domain = params.domain.trim().toLowerCase();
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(domain)) {
      throw new BadRequestException({ error: 'invalid_domain' });
    }
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.domains (client_id, domain, status)
       VALUES ($1::uuid, $2, 'pending')
       ON CONFLICT (client_id, domain) DO UPDATE SET domain = EXCLUDED.domain
       RETURNING id::text`,
      [params.clientId, domain],
    );
    const id = String(result.rows[0].id);
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'domain_registered',
      entityType: 'domain',
      entityId: id,
      after: { domain },
    });
    const updated = await this.getDomain(id);
    if (!updated) throw new NotFoundException({ error: 'domain_not_found' });
    return updated;
  }

  async verifyDomain(id: string, actor: string): Promise<EmailDeliverabilityDomainRow> {
    const domain = await this.getDomain(id);
    if (!domain) throw new NotFoundException({ error: 'domain_not_found' });
    const dnsResult = await this.verifyDomainDns(domain.domain);
    const status = dnsResult.spf_status === 'pass' ? 'active' : 'pending';
    const warmStage = dnsResult.spf_status === 'pass' ? 1 : 0;
    await this.db.query(
      `UPDATE ${SCHEMA}.domains
       SET spf_status = $2, dkim_status = $3, dmarc_status = $4,
           last_checked_at = NOW(), status = $5,
           warm_up_stage = GREATEST(warm_up_stage, $6)
       WHERE id = $1::uuid`,
      [id, dnsResult.spf_status, dnsResult.dkim_status, dnsResult.dmarc_status, status, warmStage],
    );
    await this.audit({
      clientId: domain.client_id,
      actor,
      action: 'domain_dns_verified',
      entityType: 'domain',
      entityId: id,
      after: dnsResult,
    });
    const updated = await this.getDomain(id);
    if (!updated) throw new NotFoundException({ error: 'domain_not_found' });
    return updated;
  }

  private async resolveTxt(name: string): Promise<string[]> {
    try {
      const rows = await dns.resolveTxt(name);
      return rows.map((parts) => parts.join(''));
    } catch {
      return [];
    }
  }

  private async verifyDomainDns(domainName: string): Promise<{
    domain: string;
    spf_status: string;
    dkim_status: string;
    dmarc_status: string;
    records_found: number;
  }> {
    const domain = domainName.trim().toLowerCase();
    if (!domain || !domain.includes('.')) {
      return {
        domain,
        spf_status: 'fail',
        dkim_status: 'fail',
        dmarc_status: 'fail',
        records_found: 0,
      };
    }
    const rootTxt = await this.resolveTxt(domain);
    const spfStatus = rootTxt.some((t) => t.toLowerCase().includes('v=spf1')) ? 'pass' : 'fail';
    const dkimTxt = await this.resolveTxt(`s1._domainkey.${domain}`);
    const dkimStatus = dkimTxt.length > 0 ? 'pass' : 'warn';
    const dmarcTxt = await this.resolveTxt(`_dmarc.${domain}`);
    let dmarcStatus = dmarcTxt.some((t) => t.toLowerCase().includes('v=dmarc1')) ? 'pass' : 'warn';
    if (dmarcTxt.some((t) => /p=none/i.test(t))) {
      dmarcStatus = 'warn';
    }
    return {
      domain,
      spf_status: spfStatus,
      dkim_status: dkimStatus,
      dmarc_status: dmarcStatus,
      records_found: rootTxt.length + dkimTxt.length + dmarcTxt.length,
    };
  }

  async revenueAttributed(params: { clientId?: string; days: number }): Promise<number> {
    const safeDays = Math.max(1, Math.min(params.days, 365));
    const { sql } = revenueAttributedQuery(params.clientId ? 2 : undefined);
    const values: unknown[] = [safeDays];
    if (params.clientId) values.push(params.clientId);
    try {
      const result = await this.db.query<{ total: string }>(sql, values);
      return Math.round(Number(result.rows[0]?.total ?? 0) * 100) / 100;
    } catch {
      return 0;
    }
  }

  async pauseDomain(id: string, actor: string): Promise<EmailDeliverabilityDomainRow> {
    const domain = await this.getDomain(id);
    if (!domain) throw new NotFoundException({ error: 'domain_not_found' });
    await this.db.query(
      `UPDATE ${SCHEMA}.domains SET status = 'paused' WHERE id = $1::uuid`,
      [id],
    );
    await this.audit({
      clientId: domain.client_id,
      actor,
      action: 'domain_paused',
      entityType: 'domain',
      entityId: id,
    });
    const updated = await this.getDomain(id);
    if (!updated) throw new NotFoundException({ error: 'domain_not_found' });
    return updated;
  }

  async reportsSummary(params: { clientId?: string; days: number }): Promise<EmailReportsSummary> {
    const values: unknown[] = [params.days];
    let clientClause = '';
    if (params.clientId) {
      values.push(params.clientId);
      clientClause = ' AND sq.client_id = $2::uuid';
    }
    const sent = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.send_queue sq
       WHERE sq.status IN ('sent', 'delivered')
         AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - ($1::int || ' days')::interval${clientClause}`,
      values,
    );
    const delivered = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.event_type = 'delivered'
         AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/sq\.client_id/g, 'ee.client_id')}`,
      values,
    );
    const opens = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.event_type = 'open'
         AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/sq\.client_id/g, 'ee.client_id')}`,
      values,
    );
    const clicks = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.event_type = 'click'
         AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/sq\.client_id/g, 'ee.client_id')}`,
      values,
    );
    const unsubs = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.event_type = 'unsubscribe'
         AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/sq\.client_id/g, 'ee.client_id')}`,
      values,
    );
    const sentCount = Number(sent.rows[0]?.c ?? 0);
    const deliveredCount = Number(delivered.rows[0]?.c ?? 0);
    const openCount = Number(opens.rows[0]?.c ?? 0);
    const clickCount = Number(clicks.rows[0]?.c ?? 0);
    const unsubCount = Number(unsubs.rows[0]?.c ?? 0);
    return {
      ok: true,
      days: params.days,
      client_id: params.clientId ?? null,
      sent: sentCount,
      delivered: deliveredCount,
      opens: openCount,
      clicks: clickCount,
      unsubscribes: unsubCount,
      open_rate_pct: sentCount > 0 ? Math.round((10000 * openCount) / sentCount) / 100 : 0,
      click_rate_pct: sentCount > 0 ? Math.round((10000 * clickCount) / sentCount) / 100 : 0,
      revenue_attrib: await this.revenueAttributed({
        clientId: params.clientId,
        days: params.days,
      }),
    };
  }

  async campaignReport(campaignId: string): Promise<EmailReportsCampaignStats> {
    const camp = await this.db.query(
      `SELECT cam.id, cam.client_id, cam.name, cam.audience_count, cam.status,
              cam.sent_at, cl.name AS client_name
       FROM ${SCHEMA}.campaigns cam
       JOIN clients cl ON cl.id = cam.client_id
       WHERE cam.id = $1::uuid`,
      [campaignId],
    );
    if (!camp.rowCount) throw new NotFoundException({ error: 'campaign_not_found' });
    const row = camp.rows[0];
    const stats = await this.db.query<{ event_type: string; c: string }>(
      `SELECT ee.event_type, COUNT(*) AS c
       FROM ${SCHEMA}.engagement_events ee
       JOIN ${SCHEMA}.send_queue sq ON sq.id = ee.send_id
       WHERE sq.campaign_id = $1::uuid
       GROUP BY ee.event_type`,
      [campaignId],
    );
    const byType: Record<string, number> = {};
    for (const s of stats.rows) {
      byType[String(s.event_type)] = Number(s.c);
    }
    const sent = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.send_queue WHERE campaign_id = $1::uuid AND status IN ('sent','delivered')`,
      [campaignId],
    );
    const sentCount = Number(sent.rows[0]?.c ?? 0);
    return {
      ok: true,
      campaign_id: String(row.id),
      campaign_name: String(row.name),
      client_id: String(row.client_id),
      client_name: String(row.client_name),
      status: String(row.status),
      audience_count: row.audience_count == null ? null : Number(row.audience_count),
      sent: sentCount,
      delivered: byType.delivered ?? 0,
      opens: byType.open ?? 0,
      clicks: byType.click ?? 0,
      unsubscribes: byType.unsubscribe ?? 0,
      complaints: byType.complaint ?? 0,
      bounces: (byType.bounce_hard ?? 0) + (byType.bounce_soft ?? 0),
    };
  }

  async deliverabilityReport(params: {
    clientId?: string;
    days: number;
  }): Promise<EmailDeliverabilityReport> {
    const domains = await this.listDomains({
      clientId: params.clientId,
      limit: 100,
      offset: 0,
    });
    const values: unknown[] = [params.days];
    let clientClause = '';
    if (params.clientId) {
      values.push(params.clientId);
      clientClause = ' AND ee.client_id = $2::uuid';
    }
    const bounce = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.event_type IN ('bounce_hard', 'bounce_soft')
         AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause}`,
      values,
    );
    const complaint = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.event_type = 'complaint'
         AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause}`,
      values,
    );
    const sent = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.send_queue sq
       WHERE sq.status IN ('sent', 'delivered')
         AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/ee\.client_id/g, 'sq.client_id')}`,
      values,
    );
    const sentCount = Number(sent.rows[0]?.c ?? 0);
    const bounceCount = Number(bounce.rows[0]?.c ?? 0);
    const complaintCount = Number(complaint.rows[0]?.c ?? 0);
    return {
      ok: true,
      days: params.days,
      client_id: params.clientId ?? null,
      domains: domains.items,
      bounce_rate_pct: sentCount > 0 ? Math.round((10000 * bounceCount) / sentCount) / 100 : 0,
      complaint_rate_pct: sentCount > 0 ? Math.round((10000 * complaintCount) / sentCount) / 100 : 0,
      paused_domains: domains.items.filter((d) => d.status === 'paused').length,
    };
  }

  async engagementSeries(params: {
    clientId?: string;
    days: number;
  }): Promise<{ ok: boolean; points: EmailEngagementSeriesPoint[] }> {
    const values: unknown[] = [params.days];
    let clientClause = '';
    if (params.clientId) {
      values.push(params.clientId);
      clientClause = ' AND ee.client_id = $2::uuid';
    }
    const result = await this.db.query<{ day: string; opens: string; clicks: string }>(
      `SELECT DATE(ee.occurred_at) AS day,
              COUNT(*) FILTER (WHERE ee.event_type = 'open') AS opens,
              COUNT(*) FILTER (WHERE ee.event_type = 'click') AS clicks
       FROM ${SCHEMA}.engagement_events ee
       WHERE ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause}
       GROUP BY DATE(ee.occurred_at)
       ORDER BY day ASC`,
      values,
    );
    return {
      ok: true,
      points: result.rows.map((r) => ({
        date: String(r.day).slice(0, 10),
        opens: Number(r.opens ?? 0),
        clicks: Number(r.clicks ?? 0),
      })),
    };
  }

  private defaultGraph(entrySegmentId?: string): Record<string, unknown> {
    return {
      nodes: [
        {
          id: 'trigger',
          type: 'trigger',
          config: { trigger_type: 'segment_enter', segment_id: entrySegmentId ?? null },
        },
        { id: 'wait_1', type: 'wait', config: { delay_hours: 24 } },
        { id: 'send_1', type: 'send', config: { template_id: null } },
      ],
      edges: [
        { from: 'trigger', to: 'wait_1' },
        { from: 'wait_1', to: 'send_1' },
      ],
    };
  }

  async getReportSchedule(id: string): Promise<EmailReportScheduleRow> {
    const row = await this.fetchReportSchedule(id);
    if (!row) throw new NotFoundException({ error: 'schedule_not_found' });
    return row;
  }

  async listReportSchedules(params: {
    clientId: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailReportScheduleRow>> {
    const { limit, offset } = EmailMarketingEnterpriseRepository.pagination(params.limit, params.offset);
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.report_schedules WHERE client_id = $1::uuid`,
      [params.clientId],
    );
    const result = await this.db.query(
      `SELECT rs.*, cl.name AS client_name
       FROM ${SCHEMA}.report_schedules rs
       JOIN clients cl ON cl.id = rs.client_id
       WHERE rs.client_id = $1::uuid
       ORDER BY rs.created_at DESC
       LIMIT $2 OFFSET $3`,
      [params.clientId, limit, offset],
    );
    return {
      ok: true,
      items: result.rows.map((r) => this.mapReportSchedule(r)),
      total: Number(count.rows[0]?.c ?? 0),
      limit,
      offset,
    };
  }

  async createReportSchedule(params: {
    clientId: string;
    reportType?: string;
    cadence?: string;
    dayOfWeek?: number;
    dayOfMonth?: number;
    recipientEmails?: string[];
    ccEmails?: string[];
    bccEmails?: string[];
    actor: string;
  }): Promise<EmailReportScheduleRow> {
    const reportType = params.reportType ?? 'executive';
    const cadence = params.cadence ?? 'weekly';
    if (!['executive', 'campaign', 'deliverability'].includes(reportType)) {
      throw new BadRequestException({ error: 'invalid_report_type' });
    }
    if (!['weekly', 'monthly'].includes(cadence)) {
      throw new BadRequestException({ error: 'invalid_cadence' });
    }
    const nextRun = this.computeNextRun(
      cadence,
      params.dayOfWeek ?? 0,
      params.dayOfMonth ?? 1,
    );
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.report_schedules (
         client_id, report_type, cadence, day_of_week, day_of_month,
         recipient_emails_json, cc_emails_json, bcc_emails_json, next_run_at
       ) VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9::date)
       RETURNING id`,
      [
        params.clientId,
        reportType,
        cadence,
        params.dayOfWeek ?? 0,
        params.dayOfMonth ?? 1,
        JSON.stringify(params.recipientEmails ?? []),
        JSON.stringify(params.ccEmails ?? []),
        JSON.stringify(params.bccEmails ?? []),
        nextRun,
      ],
    );
    const id = String(result.rows[0]?.id ?? '');
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'report_schedule_created',
      entityType: 'report_schedule',
      entityId: id,
    });
    const row = await this.fetchReportSchedule(id);
    if (!row) throw new NotFoundException({ error: 'schedule_not_found' });
    return row;
  }

  async updateReportSchedule(
    id: string,
    patch: Record<string, unknown>,
    actor: string,
  ): Promise<EmailReportScheduleRow> {
    const existing = await this.fetchReportSchedule(id);
    if (!existing) throw new NotFoundException({ error: 'schedule_not_found' });
    const active = patch.active != null ? Boolean(patch.active) : existing.active;
    const cadence = String(patch.cadence ?? existing.cadence);
    const dayOfWeek = patch.day_of_week != null ? Number(patch.day_of_week) : existing.day_of_week;
    const dayOfMonth = patch.day_of_month != null ? Number(patch.day_of_month) : existing.day_of_month;
    const nextRun =
      patch.next_run_at != null
        ? String(patch.next_run_at).slice(0, 10)
        : this.computeNextRun(cadence, dayOfWeek, dayOfMonth);
    await this.db.query(
      `UPDATE ${SCHEMA}.report_schedules
       SET active = $2,
           cadence = $3,
           day_of_week = $4,
           day_of_month = $5,
           recipient_emails_json = COALESCE($6::jsonb, recipient_emails_json),
           cc_emails_json = COALESCE($7::jsonb, cc_emails_json),
           bcc_emails_json = COALESCE($8::jsonb, bcc_emails_json),
           next_run_at = $9::date,
           updated_at = NOW()
       WHERE id = $1::uuid`,
      [
        id,
        active,
        cadence,
        dayOfWeek,
        dayOfMonth,
        patch.recipient_emails != null ? JSON.stringify(patch.recipient_emails) : null,
        patch.cc_emails != null ? JSON.stringify(patch.cc_emails) : null,
        patch.bcc_emails != null ? JSON.stringify(patch.bcc_emails) : null,
        nextRun,
      ],
    );
    await this.audit({
      clientId: existing.client_id,
      actor,
      action: 'report_schedule_updated',
      entityType: 'report_schedule',
      entityId: id,
    });
    const updated = await this.fetchReportSchedule(id);
    if (!updated) throw new NotFoundException({ error: 'schedule_not_found' });
    return updated;
  }

  async deleteReportSchedule(id: string, actor: string): Promise<{ ok: boolean }> {
    const existing = await this.fetchReportSchedule(id);
    if (!existing) throw new NotFoundException({ error: 'schedule_not_found' });
    await this.db.query(`DELETE FROM ${SCHEMA}.report_schedules WHERE id = $1::uuid`, [id]);
    await this.audit({
      clientId: existing.client_id,
      actor,
      action: 'report_schedule_deleted',
      entityType: 'report_schedule',
      entityId: id,
    });
    return { ok: true };
  }

  private async fetchReportSchedule(id: string): Promise<EmailReportScheduleRow | null> {
    const result = await this.db.query(
      `SELECT rs.*, cl.name AS client_name
       FROM ${SCHEMA}.report_schedules rs
       JOIN clients cl ON cl.id = rs.client_id
       WHERE rs.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    return this.mapReportSchedule(result.rows[0]);
  }

  private computeNextRun(cadence: string, dayOfWeek: number, dayOfMonth: number, fromDate = new Date()): string {
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

  private mapReportSchedule(r: Record<string, unknown>): EmailReportScheduleRow {
    const parseEmails = (raw: unknown): string[] => {
      if (Array.isArray(raw)) return raw.map(String).filter(Boolean);
      try {
        const data = JSON.parse(String(raw ?? '[]'));
        return Array.isArray(data) ? data.map(String).filter(Boolean) : [];
      } catch {
        return [];
      }
    };
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      report_type: String(r.report_type ?? 'executive'),
      cadence: String(r.cadence ?? 'weekly'),
      day_of_week: Number(r.day_of_week ?? 0),
      day_of_month: Number(r.day_of_month ?? 1),
      recipient_emails: parseEmails(r.recipient_emails_json),
      cc_emails: parseEmails(r.cc_emails_json),
      bcc_emails: parseEmails(r.bcc_emails_json),
      active: Boolean(r.active),
      next_run_at: r.next_run_at ? String(r.next_run_at).slice(0, 10) : null,
      last_sent_at: iso(r.last_sent_at),
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
    };
  }

  private async syncJourneySteps(journeyId: string, graph: Record<string, unknown>): Promise<void> {
    await this.db.query(`DELETE FROM ${SCHEMA}.journey_steps WHERE journey_id = $1::uuid`, [journeyId]);
    const nodes = (graph.nodes ?? []) as GraphNode[];
    let order = 0;
    for (const node of nodes) {
      if (!node?.id || !node?.type) continue;
      await this.db.query(
        `INSERT INTO ${SCHEMA}.journey_steps (journey_id, step_key, step_type, config_json, sort_order)
         VALUES ($1::uuid, $2, $3, $4::jsonb, $5)`,
        [journeyId, node.id, node.type, JSON.stringify(node.config ?? {}), order++],
      );
    }
  }

  private async getDomain(id: string): Promise<EmailDeliverabilityDomainRow | null> {
    const result = await this.db.query(
      `SELECT d.id, d.client_id, cl.name AS client_name, d.domain,
              d.spf_status, d.dkim_status, d.dmarc_status, d.last_checked_at,
              d.warm_up_stage, d.daily_volume_cap, d.status, d.created_at
       FROM ${SCHEMA}.domains d
       JOIN clients cl ON cl.id = d.client_id
       WHERE d.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    return this.mapDomain(result.rows[0]);
  }

  private mapJourney(r: Record<string, unknown>): EmailJourneyRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      name: String(r.name ?? ''),
      trigger_type: String(r.trigger_type ?? 'segment_enter'),
      graph_json: (r.graph_json ?? { nodes: [], edges: [] }) as Record<string, unknown>,
      entry_segment_id: r.entry_segment_id ? String(r.entry_segment_id) : null,
      entry_segment_name: r.entry_segment_name ? String(r.entry_segment_name) : null,
      status: String(r.status ?? 'draft'),
      enrolled_count: Number(r.enrolled_count ?? 0),
      created_by: r.created_by ? String(r.created_by) : null,
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
      steps: [],
    };
  }

  private mapJourneyStep(r: Record<string, unknown>): EmailJourneyStepRow {
    return {
      id: String(r.id),
      journey_id: String(r.journey_id),
      step_key: String(r.step_key),
      step_type: String(r.step_type),
      config_json: (r.config_json ?? {}) as Record<string, unknown>,
      sort_order: Number(r.sort_order ?? 0),
      created_at: iso(r.created_at) ?? '',
    };
  }

  private mapDomain(r: Record<string, unknown>): EmailDeliverabilityDomainRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      domain: String(r.domain ?? ''),
      spf_status: String(r.spf_status ?? 'unknown'),
      dkim_status: String(r.dkim_status ?? 'unknown'),
      dmarc_status: String(r.dmarc_status ?? 'unknown'),
      last_checked_at: iso(r.last_checked_at),
      warm_up_stage: Number(r.warm_up_stage ?? 0),
      daily_volume_cap: r.daily_volume_cap == null ? null : Number(r.daily_volume_cap),
      status: String(r.status ?? 'pending'),
      created_at: iso(r.created_at) ?? '',
    };
  }
}
