import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { formatDateOnly, parseDate, resolveDateWindow, toNumber } from '../performance/performance.util';
import { B10_ANOMALY_TYPES, B11_STAT_ANOMALY_TYPES } from './meta-intelligence.util';

export interface CampaignDayMetricRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  external_campaign_id: string;
  external_campaign_name: string | null;
  performance_date: string;
  spend: number;
  leads_crm: number;
  conversion_value: number;
  target_cpl_vnd: number | null;
}

export interface CampaignWindowRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  external_campaign_id: string;
  external_campaign_name: string | null;
  spend: number;
  leads_crm: number;
  conversion_value: number;
  target_cpl_vnd: number | null;
  day_count: number;
}

@Injectable()
export class MetaIntelligenceRepository implements OnModuleDestroy {
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

  async pgDailyPerformanceReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'daily_performance'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async pgMetaAlertsReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'meta_alerts'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async fetchAttributionContext(params: {
    clientId?: string;
    dateFrom: string;
    dateTo: string;
  }): Promise<{ unmappedSpendPct: number; throughDate: string; syncedAt: string | null }> {
    const clauses = [`dp.channel = 'meta'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const values: unknown[] = [params.dateFrom, params.dateTo];
    if (params.clientId) {
      clauses.push(`dp.client_id = $3::uuid`);
      values.push(params.clientId);
    }

    const perf = await this.db.query(
      `SELECT COALESCE(SUM(dp.spend) FILTER (WHERE dp.hub_campaign_map_id IS NULL), 0) AS unmapped_spend,
              COALESCE(SUM(dp.spend), 0) AS total_spend,
              MAX(dp.performance_date)::date AS through_date
       FROM daily_performance dp
       WHERE ${clauses.join(' AND ')}`,
      values,
    );
    const row = perf.rows[0];
    const unmapped = toNumber(row?.unmapped_spend);
    const total = toNumber(row?.total_spend);
    const throughDate = row?.through_date ? formatDateOnly(new Date(String(row.through_date))) : params.dateTo;
    const unmappedSpendPct = total > 0 ? Math.round((unmapped / total) * 1000) / 10 : 0;

    let syncedAt: string | null = null;
    const syncClauses = [`j.job_type = 'meta_insights_sync'`, `j.status = 'done'`];
    const syncValues: unknown[] = [];
    if (params.clientId) {
      syncClauses.push(`j.payload->>'client_id' = $1`);
      syncValues.push(params.clientId);
    }
    try {
      const sync = await this.db.query(
        `SELECT MAX(j.finished_at) AS synced_at
         FROM jobs j
         WHERE ${syncClauses.join(' AND ')}`,
        syncValues,
      );
      syncedAt = sync.rows[0]?.synced_at ? new Date(String(sync.rows[0].synced_at)).toISOString() : null;
    } catch {
      syncedAt = null;
    }

    return { unmappedSpendPct, throughDate, syncedAt };
  }

  async listStoredAnomalies(params: { clientId?: string; limit: number }) {
    if (!(await this.pgMetaAlertsReady())) return [];
    const clauses = [`ma.channel = 'meta'`, `ma.alert_type = ANY($1::text[])`];
    const values: unknown[] = [B10_ANOMALY_TYPES];
    let idx = 2;
    if (params.clientId) {
      clauses.push(`ma.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    values.push(Math.min(Math.max(params.limit, 1), 500));

    const result = await this.db.query(
      `SELECT ma.id, ma.client_id, ma.external_campaign_id, ma.alert_type, ma.severity,
              ma.metric_value, ma.threshold_value, ma.message, ma.performance_date, ma.created_at,
              c.code AS client_code, c.name AS client_name
       FROM meta_alerts ma
       JOIN clients c ON c.id = ma.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY ma.created_at DESC
       LIMIT $${idx}`,
      values,
    );
    return result.rows;
  }

  async listCampaignDayMetrics(params: {
    clientId?: string;
    dateFrom: string;
    dateTo: string;
  }): Promise<CampaignDayMetricRow[]> {
    const clauses = [`dp.channel = 'meta'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const values: unknown[] = [params.dateFrom, params.dateTo];
    if (params.clientId) {
      clauses.push(`dp.client_id = $3::uuid`);
      values.push(params.clientId);
    }

    const result = await this.db.query(
      `SELECT dp.client_id::text,
              c.code,
              c.name,
              dp.external_campaign_id,
              MAX(hcm.external_campaign_name) AS external_campaign_name,
              dp.performance_date::date,
              SUM(dp.spend) AS spend,
              SUM(dp.leads_crm) AS leads_crm,
              SUM(dp.conversion_value) AS conversion_value,
              MAX(hcm.target_cpl_vnd) AS target_cpl_vnd
       FROM daily_performance dp
       JOIN clients c ON c.id = dp.client_id
       LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
       WHERE ${clauses.join(' AND ')}
       GROUP BY dp.client_id, c.code, c.name, dp.external_campaign_id, dp.performance_date
       ORDER BY dp.performance_date DESC`,
      values,
    );

    return result.rows.map((row) => ({
      client_id: String(row.client_id),
      client_code: row.code != null ? String(row.code) : null,
      client_name: row.name != null ? String(row.name) : null,
      external_campaign_id: String(row.external_campaign_id ?? ''),
      external_campaign_name: row.external_campaign_name != null ? String(row.external_campaign_name) : null,
      performance_date: formatDateOnly(new Date(String(row.performance_date))),
      spend: toNumber(row.spend),
      leads_crm: Math.round(toNumber(row.leads_crm)),
      conversion_value: toNumber(row.conversion_value),
      target_cpl_vnd: row.target_cpl_vnd != null ? toNumber(row.target_cpl_vnd) : null,
    }));
  }

  async listCampaignWindowMetrics(params: {
    clientId?: string;
    dateFrom: string;
    dateTo: string;
  }): Promise<CampaignWindowRow[]> {
    const clauses = [`dp.channel = 'meta'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const values: unknown[] = [params.dateFrom, params.dateTo];
    if (params.clientId) {
      clauses.push(`dp.client_id = $3::uuid`);
      values.push(params.clientId);
    }

    const result = await this.db.query(
      `SELECT dp.client_id::text,
              c.code,
              c.name,
              dp.external_campaign_id,
              MAX(hcm.external_campaign_name) AS external_campaign_name,
              SUM(dp.spend) AS spend,
              SUM(dp.leads_crm) AS leads_crm,
              SUM(dp.conversion_value) AS conversion_value,
              MAX(hcm.target_cpl_vnd) AS target_cpl_vnd,
              COUNT(DISTINCT dp.performance_date) AS day_count
       FROM daily_performance dp
       JOIN clients c ON c.id = dp.client_id
       LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
       WHERE ${clauses.join(' AND ')}
       GROUP BY dp.client_id, c.code, c.name, dp.external_campaign_id
       HAVING SUM(dp.spend) > 0`,
      values,
    );

    return result.rows.map((row) => ({
      client_id: String(row.client_id),
      client_code: row.code != null ? String(row.code) : null,
      client_name: row.name != null ? String(row.name) : null,
      external_campaign_id: String(row.external_campaign_id ?? ''),
      external_campaign_name: row.external_campaign_name != null ? String(row.external_campaign_name) : null,
      spend: toNumber(row.spend),
      leads_crm: Math.round(toNumber(row.leads_crm)),
      conversion_value: toNumber(row.conversion_value),
      target_cpl_vnd: row.target_cpl_vnd != null ? toNumber(row.target_cpl_vnd) : null,
      day_count: Math.max(1, Math.round(toNumber(row.day_count))),
    }));
  }

  async listRoasDailySeries(params: { clientId?: string; dateFrom: string; dateTo: string }) {
    const clauses = [`dp.channel = 'meta'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const values: unknown[] = [params.dateFrom, params.dateTo];
    if (params.clientId) {
      clauses.push(`dp.client_id = $3::uuid`);
      values.push(params.clientId);
    }

    const result = await this.db.query(
      `SELECT dp.performance_date::date,
              SUM(dp.spend) AS spend,
              SUM(dp.conversion_value) AS conversion_value
       FROM daily_performance dp
       WHERE ${clauses.join(' AND ')}
       GROUP BY dp.performance_date
       ORDER BY dp.performance_date ASC`,
      values,
    );
    return result.rows;
  }

  resolveWindow(query: { from?: string; to?: string; days?: string }, defaultDays = 7) {
    const daysNum = query.days ? Number(query.days) : defaultDays;
    const windowDays = Number.isFinite(daysNum) ? Math.max(1, Math.min(daysNum, 90)) : defaultDays;
    return resolveDateWindow(
      { date_from: query.from, date_to: query.to },
      windowDays,
    );
  }

  formatWindow(start: Date, end: Date) {
    return { dateFrom: formatDateOnly(start), dateTo: formatDateOnly(end) };
  }

  parseOptionalDate(value: string | undefined, fallback: Date): Date {
    return parseDate(value, fallback);
  }

  async pgInsightLevelColumnReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'daily_performance'
           AND column_name = 'insight_level'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async listDailyInsights(params: {
    clientId?: string;
    level: string;
    dateFrom: string;
    dateTo: string;
    limit?: number;
  }) {
    const hasLevelCol = await this.pgInsightLevelColumnReady();
    const clauses = [`dp.channel = 'meta'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const values: unknown[] = [params.dateFrom, params.dateTo];
    let idx = 3;

    if (hasLevelCol) {
      clauses.push(`dp.insight_level = $${idx++}`);
      values.push(params.level);
    } else if (params.level !== 'campaign') {
      return { rows: [], hasLevelCol: false };
    }

    if (params.clientId) {
      clauses.push(`dp.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }

    const limit = Math.min(Math.max(params.limit ?? 500, 1), 2000);
    values.push(limit);

    const adsetSelect = hasLevelCol
      ? `, dp.external_adset_id, dp.external_adset_name, dp.insight_level`
      : `, '' AS external_adset_id, NULL::varchar AS external_adset_name, 'campaign' AS insight_level`;

    const result = await this.db.query(
      `SELECT dp.client_id::text,
              c.code AS client_code,
              c.name AS client_name,
              dp.external_campaign_id,
              dp.external_campaign_name,
              dp.performance_date::date,
              dp.spend,
              dp.impressions,
              dp.clicks,
              dp.leads_crm,
              dp.conversion_value
              ${adsetSelect}
       FROM daily_performance dp
       JOIN clients c ON c.id = dp.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY dp.performance_date DESC, dp.spend DESC
       LIMIT $${idx}`,
      values,
    );

    return { rows: result.rows, hasLevelCol };
  }

  async listStoredStatAnomalies(params: { clientId?: string; limit: number }) {
    if (!(await this.pgMetaAlertsReady())) return [];
    const clauses = [`ma.channel = 'meta'`, `ma.alert_type = ANY($1::text[])`];
    const values: unknown[] = [B11_STAT_ANOMALY_TYPES];
    let idx = 2;
    if (params.clientId) {
      clauses.push(`ma.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    values.push(Math.min(Math.max(params.limit, 1), 500));

    const result = await this.db.query(
      `SELECT ma.id, ma.client_id, ma.external_campaign_id, ma.alert_type, ma.severity,
              ma.metric_value, ma.threshold_value, ma.message, ma.performance_date, ma.created_at,
              c.code AS client_code, c.name AS client_name
       FROM meta_alerts ma
       JOIN clients c ON c.id = ma.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY ma.created_at DESC
       LIMIT $${idx}`,
      values,
    );
    return result.rows;
  }

  async listDailyMetricSeries(params: {
    clientId?: string;
    dateFrom: string;
    dateTo: string;
    metric: 'cpl' | 'spend';
  }) {
    const clauses = [`dp.channel = 'meta'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const values: unknown[] = [params.dateFrom, params.dateTo];
    if (params.clientId) {
      clauses.push(`dp.client_id = $3::uuid`);
      values.push(params.clientId);
    }

    const result = await this.db.query(
      `SELECT dp.performance_date::date,
              SUM(dp.spend) AS spend,
              SUM(dp.leads_crm) AS leads_crm
       FROM daily_performance dp
       WHERE ${clauses.join(' AND ')}
       GROUP BY dp.performance_date
       ORDER BY dp.performance_date ASC`,
      values,
    );

    return result.rows.map((row) => {
      const spend = toNumber(row.spend);
      const leads = Math.round(toNumber(row.leads_crm));
      const value = params.metric === 'spend' ? spend : leads > 0 ? spend / leads : 0;
      return {
        performance_date: formatDateOnly(new Date(String(row.performance_date))),
        value,
      };
    });
  }

  async pgMetaPixelsReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'meta_pixels'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async pgMetaIntelligenceSnapshotsReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'meta_intelligence_snapshots'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async listMetaPixels(params: { clientId?: string; channelAccountId?: string }) {
    const clauses = ['1=1'];
    const values: unknown[] = [];
    let idx = 1;
    if (params.channelAccountId) {
      clauses.push(`mp.client_channel_account_id = $${idx++}::uuid`);
      values.push(params.channelAccountId);
    }
    if (params.clientId) {
      clauses.push(`cca.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }

    const result = await this.db.query(
      `SELECT mp.id::text, mp.client_channel_account_id::text, cca.client_id::text,
              mp.pixel_id, mp.label, mp.is_primary, mp.capi_enabled, mp.created_at
       FROM meta_pixels mp
       JOIN client_channel_accounts cca ON cca.id = mp.client_channel_account_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY mp.is_primary DESC, mp.created_at ASC`,
      values,
    );
    return result.rows;
  }

  async insertMetaPixel(params: {
    clientChannelAccountId: string;
    pixelId: string;
    label: string;
    isPrimary: boolean;
    capiEnabled: boolean;
  }) {
    const client = await this.db.connect();
    try {
      await client.query('BEGIN');
      if (params.isPrimary) {
        await client.query(
          `UPDATE meta_pixels SET is_primary = FALSE WHERE client_channel_account_id = $1::uuid`,
          [params.clientChannelAccountId],
        );
      }
      const result = await client.query(
        `INSERT INTO meta_pixels (
           client_channel_account_id, pixel_id, label, is_primary, capi_enabled
         ) VALUES ($1::uuid, $2, $3, $4, $5)
         RETURNING id::text, client_channel_account_id::text, pixel_id, label, is_primary, capi_enabled, created_at`,
        [
          params.clientChannelAccountId,
          params.pixelId,
          params.label,
          params.isPrimary,
          params.capiEnabled,
        ],
      );
      await client.query('COMMIT');
      return result.rows[0];
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  async patchMetaPixel(
    pixelId: string,
    updates: { label?: string; isPrimary?: boolean; capiEnabled?: boolean },
  ) {
    const client = await this.db.connect();
    try {
      await client.query('BEGIN');
      const existing = await client.query(
        `SELECT client_channel_account_id::text FROM meta_pixels WHERE id = $1::uuid`,
        [pixelId],
      );
      if (!existing.rows.length) {
        await client.query('ROLLBACK');
        return null;
      }
      const accountId = String(existing.rows[0].client_channel_account_id);
      if (updates.isPrimary) {
        await client.query(
          `UPDATE meta_pixels SET is_primary = FALSE WHERE client_channel_account_id = $1::uuid`,
          [accountId],
        );
      }
      const sets: string[] = [];
      const values: unknown[] = [];
      let idx = 1;
      if (updates.label != null) {
        sets.push(`label = $${idx++}`);
        values.push(updates.label);
      }
      if (updates.isPrimary != null) {
        sets.push(`is_primary = $${idx++}`);
        values.push(updates.isPrimary);
      }
      if (updates.capiEnabled != null) {
        sets.push(`capi_enabled = $${idx++}`);
        values.push(updates.capiEnabled);
      }
      values.push(pixelId);
      const result = await client.query(
        `UPDATE meta_pixels SET ${sets.join(', ')}
         WHERE id = $${idx}
         RETURNING id::text, client_channel_account_id::text, pixel_id, label, is_primary, capi_enabled, created_at`,
        values,
      );
      await client.query('COMMIT');
      return result.rows[0];
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  async insertIntelligenceSnapshot(params: {
    clientId?: string;
    periodStart: string;
    periodEnd: string;
    artifactPath: string;
    byteSize: number;
  }) {
    const result = await this.db.query(
      `INSERT INTO meta_intelligence_snapshots (
         client_id, period_start, period_end, artifact_path, byte_size, gzip
       ) VALUES ($1::uuid, $2::date, $3::date, $4, $5, TRUE)
       RETURNING id::text, client_id::text, period_start, period_end, artifact_path, byte_size, gzip, created_at`,
      [
        params.clientId ?? null,
        params.periodStart,
        params.periodEnd,
        params.artifactPath,
        params.byteSize,
      ],
    );
    return result.rows[0];
  }
}
