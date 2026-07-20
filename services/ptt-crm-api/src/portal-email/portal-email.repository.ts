import { Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { revenueAttributedQuery } from '../email-marketing/email-marketing-attribution.util';
import {
  PortalEmailApprovalRow,
  PortalEmailCampaignRow,
  PortalEmailCampaignStats,
  PortalEmailDashboard,
  PortalEmailReportsSummary,
} from './portal-email.types';

const SCHEMA = 'email_mkt';

function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function pct(num: number, den: number): number {
  if (den <= 0) return 0;
  return Math.round((10000 * num) / den) / 100;
}

@Injectable()
export class PortalEmailRepository implements OnModuleDestroy {
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

  async schemaReady(): Promise<boolean> {
    try {
      await this.db.query(`SELECT 1 FROM ${SCHEMA}.workspaces LIMIT 1`);
      return true;
    } catch {
      return false;
    }
  }

  async hasWorkspace(clientId: string): Promise<boolean> {
    const result = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.workspaces WHERE client_id = $1::uuid`,
      [clientId],
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  }

  private async revenueAttributed(clientId: string, days: number): Promise<number> {
    const safeDays = Math.max(1, Math.min(days, 365));
    const { sql } = revenueAttributedQuery(2);
    try {
      const result = await this.db.query<{ total: string }>(sql, [safeDays, clientId]);
      return Math.round(Number(result.rows[0]?.total ?? 0) * 100) / 100;
    } catch {
      return 0;
    }
  }

  async dashboard(clientId: string): Promise<PortalEmailDashboard> {
    const pending = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.campaigns
       WHERE client_id = $1::uuid AND status = 'pending_approval'`,
      [clientId],
    );
    const sent = await this.db.query<{ c: string; opens: string }>(
      `SELECT
         (SELECT COUNT(*) FROM ${SCHEMA}.send_queue sq
          WHERE sq.client_id = $1::uuid AND sq.status IN ('sent','delivered')
            AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - INTERVAL '28 days') AS c,
         (SELECT COUNT(*) FROM ${SCHEMA}.engagement_events ee
          WHERE ee.client_id = $1::uuid AND ee.event_type = 'open'
            AND ee.occurred_at >= NOW() - INTERVAL '28 days') AS opens`,
      [clientId],
    );
    const sentCount = Number(sent.rows[0]?.c ?? 0);
    const opens = Number(sent.rows[0]?.opens ?? 0);
    const recent = await this.listCampaigns(clientId, 5);
    return {
      ok: true,
      email_enabled: true,
      client_id: clientId,
      pending_approvals: Number(pending.rows[0]?.c ?? 0),
      campaigns_sent_28d: sentCount,
      open_rate_pct: pct(opens, sentCount),
      revenue_attrib: await this.revenueAttributed(clientId, 28),
      recent_campaigns: recent,
    };
  }

  async listCampaigns(clientId: string, limit = 50): Promise<PortalEmailCampaignRow[]> {
    const result = await this.db.query(
      `SELECT id, name, status, audience_count, scheduled_at, sent_at, updated_at
       FROM ${SCHEMA}.campaigns
       WHERE client_id = $1::uuid
       ORDER BY updated_at DESC
       LIMIT $2`,
      [clientId, limit],
    );
    return result.rows.map((r) => this.mapCampaign(r));
  }

  async getCampaign(clientId: string, campaignId: string): Promise<PortalEmailCampaignRow | null> {
    const result = await this.db.query(
      `SELECT id, name, status, audience_count, scheduled_at, sent_at, updated_at
       FROM ${SCHEMA}.campaigns
       WHERE client_id = $1::uuid AND id = $2::uuid`,
      [clientId, campaignId],
    );
    if (!result.rowCount) return null;
    return this.mapCampaign(result.rows[0]);
  }

  async pendingApprovals(clientId: string): Promise<PortalEmailApprovalRow[]> {
    const result = await this.db.query(
      `SELECT cam.id AS campaign_id, cam.name, cam.audience_count, cam.updated_at AS requested_at,
              cam.status, tmpl.name AS template_name
       FROM ${SCHEMA}.campaigns cam
       JOIN ${SCHEMA}.templates tmpl ON tmpl.id = cam.template_id
       WHERE cam.client_id = $1::uuid AND cam.status = 'pending_approval'
       ORDER BY cam.updated_at DESC`,
      [clientId],
    );
    return result.rows.map((r) => ({
      campaign_id: String(r.campaign_id),
      name: String(r.name ?? ''),
      audience_count: r.audience_count == null ? null : Number(r.audience_count),
      template_name: String(r.template_name ?? ''),
      requested_at: iso(r.requested_at) ?? '',
      status: String(r.status ?? 'pending_approval'),
    }));
  }

  async approvalPreview(
    clientId: string,
    campaignId: string,
  ): Promise<{
    campaign_id: string;
    name: string;
    subject_template: string;
    html_body: string;
    audience_count: number | null;
    scheduled_at: string | null;
    template_name: string;
    status: string;
  } | null> {
    const result = await this.db.query(
      `SELECT cam.id AS campaign_id, cam.name, cam.audience_count, cam.scheduled_at, cam.status,
              tmpl.name AS template_name, tmpl.subject_template, tmpl.html_body
       FROM ${SCHEMA}.campaigns cam
       JOIN ${SCHEMA}.templates tmpl ON tmpl.id = cam.template_id
       WHERE cam.client_id = $1::uuid AND cam.id = $2::uuid`,
      [clientId, campaignId],
    );
    if (!result.rowCount) return null;
    const r = result.rows[0];
    return {
      campaign_id: String(r.campaign_id),
      name: String(r.name ?? ''),
      subject_template: String(r.subject_template ?? ''),
      html_body: String(r.html_body ?? ''),
      audience_count: r.audience_count == null ? null : Number(r.audience_count),
      scheduled_at: iso(r.scheduled_at),
      template_name: String(r.template_name ?? ''),
      status: String(r.status ?? ''),
    };
  }

  async campaignStats(clientId: string, campaignId: string): Promise<PortalEmailCampaignStats> {
    const camp = await this.getCampaign(clientId, campaignId);
    if (!camp) throw new NotFoundException({ error: 'campaign_not_found' });
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
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.send_queue
       WHERE campaign_id = $1::uuid AND status IN ('sent','delivered')`,
      [campaignId],
    );
    const sentCount = Number(sent.rows[0]?.c ?? 0);
    const opens = byType.open ?? 0;
    const clicks = byType.click ?? 0;
    return {
      ok: true,
      campaign_id: camp.id,
      campaign_name: camp.name,
      status: camp.status,
      audience_count: camp.audience_count,
      sent: sentCount,
      delivered: byType.delivered ?? 0,
      opens,
      clicks,
      unsubscribes: byType.unsubscribe ?? 0,
      complaints: byType.complaint ?? 0,
      open_rate_pct: pct(opens, sentCount),
      click_rate_pct: pct(clicks, sentCount),
      revenue_attrib: await this.revenueAttributed(clientId, 28),
    };
  }

  async reportsSummary(clientId: string, days: number): Promise<PortalEmailReportsSummary> {
    const sent = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.send_queue sq
       WHERE sq.client_id = $1::uuid AND sq.status IN ('sent','delivered')
         AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - ($2::int || ' days')::interval`,
      [clientId, days],
    );
    const opens = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.client_id = $1::uuid AND ee.event_type = 'open'
         AND ee.occurred_at >= NOW() - ($2::int || ' days')::interval`,
      [clientId, days],
    );
    const clicks = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.engagement_events ee
       WHERE ee.client_id = $1::uuid AND ee.event_type = 'click'
         AND ee.occurred_at >= NOW() - ($2::int || ' days')::interval`,
      [clientId, days],
    );
    const sentCount = Number(sent.rows[0]?.c ?? 0);
    const openCount = Number(opens.rows[0]?.c ?? 0);
    const clickCount = Number(clicks.rows[0]?.c ?? 0);
    return {
      ok: true,
      client_id: clientId,
      days,
      sent: sentCount,
      opens: openCount,
      clicks: clickCount,
      open_rate_pct: pct(openCount, sentCount),
      revenue_attrib: await this.revenueAttributed(clientId, days),
    };
  }

  async approveCampaign(params: {
    clientId: string;
    campaignId: string;
    actor: string;
  }): Promise<PortalEmailCampaignRow> {
    const camp = await this.getCampaign(params.clientId, params.campaignId);
    if (!camp) throw new NotFoundException({ error: 'campaign_not_found' });
    if (camp.status !== 'pending_approval') {
      throw new NotFoundException({ error: 'not_pending_approval', status: camp.status });
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.campaigns SET status = 'approved', updated_at = NOW() WHERE id = $1::uuid`,
      [params.campaignId],
    );
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'portal_campaign_approved',
      entityId: params.campaignId,
    });
    const updated = await this.getCampaign(params.clientId, params.campaignId);
    if (!updated) throw new NotFoundException({ error: 'campaign_not_found' });
    return updated;
  }

  async rejectCampaign(params: {
    clientId: string;
    campaignId: string;
    actor: string;
    note?: string;
  }): Promise<PortalEmailCampaignRow> {
    const camp = await this.getCampaign(params.clientId, params.campaignId);
    if (!camp) throw new NotFoundException({ error: 'campaign_not_found' });
    if (camp.status !== 'pending_approval') {
      throw new NotFoundException({ error: 'not_pending_approval', status: camp.status });
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.campaigns SET status = 'draft', updated_at = NOW() WHERE id = $1::uuid`,
      [params.campaignId],
    );
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'portal_campaign_rejected',
      entityId: params.campaignId,
      after: { note: params.note ?? null },
    });
    const updated = await this.getCampaign(params.clientId, params.campaignId);
    if (!updated) throw new NotFoundException({ error: 'campaign_not_found' });
    return updated;
  }

  private async audit(params: {
    clientId: string;
    actor: string;
    action: string;
    entityId: string;
    after?: Record<string, unknown>;
  }): Promise<void> {
    await this.db.query(
      `INSERT INTO ${SCHEMA}.audit_log (client_id, actor, action, entity_type, entity_id, after_json)
       VALUES ($1::uuid, $2, $3, 'campaign', $4::uuid, $5::jsonb)`,
      [
        params.clientId,
        params.actor,
        params.action,
        params.entityId,
        JSON.stringify(params.after ?? {}),
      ],
    );
  }

  private mapCampaign(r: Record<string, unknown>): PortalEmailCampaignRow {
    return {
      id: String(r.id),
      name: String(r.name ?? ''),
      status: String(r.status ?? ''),
      audience_count: r.audience_count == null ? null : Number(r.audience_count),
      scheduled_at: iso(r.scheduled_at),
      sent_at: iso(r.sent_at),
      updated_at: iso(r.updated_at) ?? '',
    };
  }
}
