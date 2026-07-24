import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';

@Injectable()
export class MetaCreativeRegistryRepository implements OnModuleDestroy {
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

  async pgReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'meta_ad_creative_links'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [clientId]);
    return (result.rowCount ?? 0) > 0;
  }

  async getCreativeSubmission(creativeId: string) {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, status, title, asset_url, version,
              external_campaign_id, external_campaign_name
       FROM creative_submissions
       WHERE id = $1::uuid
       LIMIT 1`,
      [creativeId],
    );
    return result.rows[0] ?? null;
  }

  async findActiveLink(clientId: string, externalAdId: string) {
    const result = await this.db.query(
      `SELECT id::text FROM meta_ad_creative_links
       WHERE client_id = $1::uuid AND external_ad_id = $2 AND is_active IS TRUE
       LIMIT 1`,
      [clientId, externalAdId],
    );
    return result.rows[0]?.id ? String(result.rows[0].id) : null;
  }

  async listLinks(params: {
    clientId?: string;
    externalAdId?: string;
    externalCampaignId?: string;
    creativeSubmissionId?: string;
    activeOnly: boolean;
    limit: number;
  }) {
    const clauses = ['1=1'];
    const values: unknown[] = [];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`l.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.externalAdId) {
      clauses.push(`l.external_ad_id = $${idx++}`);
      values.push(params.externalAdId);
    }
    if (params.externalCampaignId) {
      clauses.push(`l.external_campaign_id = $${idx++}`);
      values.push(params.externalCampaignId);
    }
    if (params.creativeSubmissionId) {
      clauses.push(`l.creative_submission_id = $${idx++}::uuid`);
      values.push(params.creativeSubmissionId);
    }
    if (params.activeOnly) {
      clauses.push(`l.is_active IS TRUE`);
    }
    values.push(params.limit);

    const result = await this.db.query(
      `SELECT l.id::text, l.client_id::text, l.creative_submission_id::text,
              l.external_ad_id, l.external_adset_id, l.external_campaign_id,
              l.external_creative_id, l.link_source, l.is_active, l.linked_by, l.note,
              l.created_at, l.updated_at,
              cs.title, cs.status, cs.asset_url, cs.version
       FROM meta_ad_creative_links l
       JOIN creative_submissions cs ON cs.id = l.creative_submission_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY l.updated_at DESC
       LIMIT $${idx}`,
      values,
    );
    return result.rows;
  }

  async resolveLink(clientId: string, externalAdId: string) {
    const result = await this.db.query(
      `SELECT l.id::text, l.client_id::text, l.creative_submission_id::text,
              l.external_ad_id, l.external_adset_id, l.external_campaign_id,
              l.external_creative_id, l.link_source, l.is_active, l.linked_by, l.note,
              l.created_at, l.updated_at,
              cs.title, cs.status, cs.asset_url, cs.version
       FROM meta_ad_creative_links l
       JOIN creative_submissions cs ON cs.id = l.creative_submission_id
       WHERE l.client_id = $1::uuid AND l.external_ad_id = $2 AND l.is_active IS TRUE
       LIMIT 1`,
      [clientId, externalAdId],
    );
    return result.rows[0] ?? null;
  }

  async insertLink(params: {
    clientId: string;
    creativeSubmissionId: string;
    externalAdId: string;
    externalAdsetId?: string | null;
    externalCampaignId?: string | null;
    externalCreativeId?: string | null;
    linkSource: string;
    linkedBy?: string | null;
    note?: string | null;
  }) {
    const client = await this.db.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `UPDATE meta_ad_creative_links
         SET is_active = FALSE, updated_at = NOW()
         WHERE client_id = $1::uuid AND external_ad_id = $2 AND is_active IS TRUE`,
        [params.clientId, params.externalAdId],
      );
      const result = await client.query(
        `INSERT INTO meta_ad_creative_links (
           client_id, creative_submission_id, external_ad_id, external_adset_id,
           external_campaign_id, external_creative_id, link_source, linked_by, note
         ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9)
         RETURNING id::text, client_id::text, creative_submission_id::text,
                   external_ad_id, external_adset_id, external_campaign_id,
                   external_creative_id, link_source, is_active, linked_by, note,
                   created_at, updated_at`,
        [
          params.clientId,
          params.creativeSubmissionId,
          params.externalAdId,
          params.externalAdsetId ?? null,
          params.externalCampaignId ?? null,
          params.externalCreativeId ?? null,
          params.linkSource,
          params.linkedBy ?? null,
          params.note ?? null,
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

  async deactivateLink(linkId: string) {
    const result = await this.db.query(
      `UPDATE meta_ad_creative_links
       SET is_active = FALSE, updated_at = NOW()
       WHERE id = $1::uuid AND is_active IS TRUE
       RETURNING id::text`,
      [linkId],
    );
    return (result.rowCount ?? 0) > 0;
  }
}
