import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { MetaAlertRow } from './meta-alerts.types';

@Injectable()
export class MetaAlertsRepository implements OnModuleDestroy {
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

  private mapRow(row: Record<string, unknown>): MetaAlertRow {
    return {
      id: String(row.id),
      client_id: String(row.client_id),
      channel: String(row.channel ?? 'meta'),
      external_campaign_id: row.external_campaign_id ? String(row.external_campaign_id) : null,
      alert_type: String(row.alert_type),
      severity: String(row.severity),
      metric_value: row.metric_value != null ? Number(row.metric_value) : null,
      threshold_value: row.threshold_value != null ? Number(row.threshold_value) : null,
      message: String(row.message ?? ''),
      performance_date: row.performance_date
        ? String(row.performance_date).slice(0, 10)
        : null,
      dedupe_key: String(row.dedupe_key),
      acknowledged_at: row.acknowledged_at ? new Date(String(row.acknowledged_at)).toISOString() : null,
      created_at: new Date(String(row.created_at)).toISOString(),
      client_code: row.client_code != null ? String(row.client_code) : null,
      client_name: row.client_name != null ? String(row.client_name) : null,
    };
  }

  async listAlerts(params: {
    clientId?: string;
    openOnly?: boolean;
    limit?: number;
  }): Promise<MetaAlertRow[]> {
    const clauses = [`ma.channel = 'meta'`];
    const values: unknown[] = [];
    let idx = 1;

    if (params.clientId) {
      clauses.push(`ma.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.openOnly !== false) {
      clauses.push('ma.acknowledged_at IS NULL');
    }
    const limit = Math.min(Math.max(params.limit ?? 100, 1), 500);
    values.push(limit);

    const result = await this.db.query(
      `SELECT ma.*, c.code AS client_code, c.name AS client_name
       FROM meta_alerts ma
       JOIN clients c ON c.id = ma.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY ma.created_at DESC
       LIMIT $${idx}`,
      values,
    );
    return result.rows.map((row) => this.mapRow(row));
  }

  async acknowledgeAlert(alertId: string): Promise<MetaAlertRow | null> {
    const result = await this.db.query(
      `UPDATE meta_alerts ma
       SET acknowledged_at = COALESCE(acknowledged_at, NOW())
       FROM clients c
       WHERE ma.id = $1::uuid AND c.id = ma.client_id
       RETURNING ma.*, c.code AS client_code, c.name AS client_name`,
      [alertId],
    );
    const row = result.rows[0];
    return row ? this.mapRow(row) : null;
  }
}
