import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { SEO_AUTOMATIONS_SCHEMA, SEO_JOB_TYPES } from './seo-automations.constants';

const SCHEMA = SEO_AUTOMATIONS_SCHEMA;

@Injectable()
export class SeoAutomationsRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) this.pool = new Pool({ connectionString: this.config.databaseUrl });
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async syncRuns(limit = 50, customerId?: number) {
    const values: unknown[] = [limit];
    let sql = `SELECT id, customer_id, source, status, started_at::text, finished_at::text,
                      rows_imported, error_message
               FROM ${SCHEMA}.seo_sync_runs`;
    if (customerId != null) {
      values.unshift(customerId);
      sql += ` WHERE customer_id = $1 ORDER BY started_at DESC NULLS LAST, id DESC LIMIT $2`;
    } else {
      sql += ` ORDER BY started_at DESC NULLS LAST, id DESC LIMIT $1`;
    }
    const result = await this.db.query(sql, values);
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      source: String(row.source ?? ''),
      status: String(row.status ?? ''),
      started_at: row.started_at != null ? String(row.started_at) : null,
      finished_at: row.finished_at != null ? String(row.finished_at) : null,
      rows_imported: Number(row.rows_imported ?? 0),
      error_message: String(row.error_message ?? ''),
    }));
  }

  async recentJobs(limit = 30) {
    const types = SEO_JOB_TYPES;
    const result = await this.db.query(
      `SELECT id, job_type, status, idempotency_key, created_at::text, updated_at::text, last_error
       FROM job_queue
       WHERE job_type = ANY($1::text[])
       ORDER BY created_at DESC
       LIMIT $2`,
      [types, limit],
    );
    return result.rows.map((row) => ({
      id: String(row.id),
      job_type: String(row.job_type),
      status: String(row.status),
      idempotency_key: String(row.idempotency_key),
      created_at: row.created_at != null ? String(row.created_at) : null,
      updated_at: row.updated_at != null ? String(row.updated_at) : null,
      last_error: row.last_error != null ? String(row.last_error) : null,
    }));
  }

  async statusSummary() {
    const [syncFailed, openAlerts, pendingJobs] = await Promise.all([
      this.db.query(
        `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_sync_runs
         WHERE status IN ('failed', 'error') AND started_at >= NOW() - INTERVAL '7 days'`,
      ),
      this.db.query(`SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_alerts WHERE status = 'open'`),
      this.db.query(
        `SELECT COUNT(*) AS c FROM job_queue
         WHERE job_type = ANY($1::text[]) AND status = 'pending'`,
        [SEO_JOB_TYPES],
      ),
    ]);
    return {
      failed_sync_runs_7d: Number(syncFailed.rows[0]?.c ?? 0),
      open_alerts: Number(openAlerts.rows[0]?.c ?? 0),
      pending_seo_jobs: Number(pendingJobs.rows[0]?.c ?? 0),
      jobs_enabled: this.config.jobsEnabled,
    };
  }
}
