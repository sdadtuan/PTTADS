import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { SeoReportsRepository } from '../seo-reports/seo-reports.repository';
import { crawlReminderDays } from './seo-cron.constants';

const SCHEMA = 'seo_aeo';

@Injectable()
export class SeoCronRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(
    private readonly config: AppConfigService,
    private readonly reports: SeoReportsRepository,
  ) {}

  private get db(): Pool {
    if (!this.pool) this.pool = new Pool({ connectionString: this.config.databaseUrl });
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async listSeoCustomerIds(maxClients?: number | null): Promise<number[]> {
    const result = await this.db.query<{ customer_id: string }>(
      `SELECT DISTINCT customer_id FROM (
         SELECT customer_id FROM ${SCHEMA}.seo_client_settings
         UNION SELECT customer_id FROM ${SCHEMA}.seo_questions WHERE status = 'active'
         UNION SELECT customer_id FROM ${SCHEMA}.seo_keywords WHERE status = 'active'
       ) t ORDER BY customer_id ASC
       ${maxClients != null ? `LIMIT ${Math.max(1, maxClients)}` : ''}`,
    );
    return result.rows.map((r) => Number(r.customer_id));
  }

  async runCrawlReminders(maxAgeDays = crawlReminderDays()) {
    const rows = await this.db.query<{ customer_id: string }>(
      `SELECT DISTINCT customer_id FROM (
         SELECT customer_id FROM ${SCHEMA}.seo_client_settings
         UNION SELECT customer_id FROM ${SCHEMA}.seo_technical_issues
       ) t`,
    );
    const created: Array<{ alert_id: number; customer_id: number }> = [];
    for (const row of rows.rows) {
      const cid = Number(row.customer_id);
      const last = await this.db.query<{ imported_at: string }>(
        `SELECT imported_at FROM ${SCHEMA}.seo_crawl_import_log
         WHERE customer_id = $1 ORDER BY id DESC LIMIT 1`,
        [cid],
      );
      const lastAt = last.rows[0]?.imported_at ? String(last.rows[0].imported_at) : null;
      if (lastAt) {
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - maxAgeDays);
        if (new Date(lastAt) >= cutoff) continue;
      }
      const msg = lastAt
        ? `Chưa import crawl CSV trong ${maxAgeDays} ngày`
        : 'Chưa từng import crawl CSV — upload Screaming Frog export';
      const alertId = await this.reports.createAlert({
        customerId: cid,
        alertType: 'crawl_stale',
        severity: 'warn',
        message: msg,
        link: `/seo/technical?customer_id=${cid}`,
      });
      if (alertId) created.push({ alert_id: alertId, customer_id: cid });
    }
    return { ok: true, reminders: created.length, alerts: created };
  }

  async runCrawlScheduleChecks() {
    const rows = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_crawl_schedules WHERE active = TRUE`,
    );
    const created: Array<{ alert_id: number; customer_id: number }> = [];
    const now = new Date();
    for (const sched of rows.rows) {
      const cid = Number(sched.customer_id);
      const freq = Number(sched.frequency_days ?? 30);
      const last = sched.last_ingest_at ? new Date(String(sched.last_ingest_at)) : null;
      if (last && !Number.isNaN(last.getTime())) {
        const daysSince = Math.floor((now.getTime() - last.getTime()) / 86400000);
        if (daysSince < freq) continue;
      } else if (last) {
        continue;
      }
      const msg = last
        ? `Crawl connector quá hạn (${freq} ngày) — gửi export tới webhook`
        : 'Chưa nhận crawl webhook — cấu hình Screaming Frog / Sitebulb push';
      const alertId = await this.reports.createAlert({
        customerId: cid,
        alertType: 'crawl_connector_due',
        severity: 'warn',
        message: msg,
        link: `/seo/technical?customer_id=${cid}`,
      });
      if (alertId) created.push({ alert_id: alertId, customer_id: cid });
    }
    return { ok: true, due_alerts: created.length, alerts: created };
  }

  async recordCrawlImport(customerId: number, rowsImported: number): Promise<number> {
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_crawl_import_log (customer_id, rows_imported, imported_at)
       VALUES ($1, $2, NOW()) RETURNING id`,
      [customerId, Math.max(0, rowsImported)],
    );
    return Number(result.rows[0].id);
  }
}
