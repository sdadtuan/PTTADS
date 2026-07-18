import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { CreativeRow, CreativeStatus } from './creatives.types';

interface CreativeDbRow {
  id: string;
  client_id: string;
  title: string;
  description: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  version: number | string;
  asset_url: string | null;
  asset_type: string;
  status: CreativeStatus;
  submitted_by: string | null;
  submitted_at: Date | string;
  reviewed_by: string | null;
  reviewed_at: Date | string | null;
  review_note: string | null;
  temporal_workflow_id: string | null;
}

@Injectable()
export class CreativesRepository implements OnModuleDestroy {
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

  async pgCreativesReady(): Promise<boolean> {
    const result = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'creative_submissions'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  }

  async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [
      clientId,
    ]);
    return (result.rowCount ?? 0) > 0;
  }

  async create(input: {
    clientId: string;
    title: string;
    description: string | null;
    externalCampaignId: string | null;
    externalCampaignName: string | null;
    version: number;
    assetUrl: string | null;
    assetType: string;
    submittedBy: string;
  }): Promise<CreativeRow> {
    const result = await this.db.query(
      `INSERT INTO creative_submissions (
         client_id, title, description, external_campaign_id, external_campaign_name,
         version, asset_url, asset_type, status, submitted_by
       ) VALUES (
         $1::uuid, $2, $3, $4, $5,
         $6, $7, $8, 'pending_client', $9
       )
       RETURNING
          id::text,
          client_id::text,
          title,
          description,
          external_campaign_id,
          external_campaign_name,
          version,
          asset_url,
          asset_type,
          status,
          submitted_by,
          submitted_at,
          reviewed_by,
          reviewed_at,
          review_note,
          temporal_workflow_id`,
      [
        input.clientId,
        input.title,
        input.description,
        input.externalCampaignId,
        input.externalCampaignName,
        input.version,
        input.assetUrl,
        input.assetType,
        input.submittedBy,
      ],
    );
    return this.mapRow(result.rows[0] as CreativeDbRow);
  }

  async updateTemporalMeta(
    id: string,
    workflowId: string,
    runId: string | null,
  ): Promise<CreativeRow | null> {
    const result = await this.db.query(
      `UPDATE creative_submissions
       SET temporal_workflow_id = $2,
           temporal_run_id = $3,
           updated_at = NOW()
       WHERE id = $1::uuid
       RETURNING
          id::text,
          client_id::text,
          title,
          description,
          external_campaign_id,
          external_campaign_name,
          version,
          asset_url,
          asset_type,
          status,
          submitted_by,
          submitted_at,
          reviewed_by,
          reviewed_at,
          review_note,
          temporal_workflow_id`,
      [id, workflowId, runId],
    );
    const row = result.rows[0] as CreativeDbRow | undefined;
    return row ? this.mapRow(row) : null;
  }

  async listPending(clientId: string): Promise<CreativeRow[]> {
    const result = await this.db.query(
      `SELECT
          id::text,
          client_id::text,
          title,
          description,
          external_campaign_id,
          external_campaign_name,
          version,
          asset_url,
          asset_type,
          status,
          submitted_by,
          submitted_at,
          reviewed_by,
          reviewed_at,
          review_note,
          temporal_workflow_id
        FROM creative_submissions
        WHERE client_id = $1::uuid AND status = 'pending_client'
        ORDER BY submitted_at DESC`,
      [clientId],
    );
    return (result.rows as CreativeDbRow[]).map((row) => this.mapRow(row));
  }

  async findById(id: string): Promise<CreativeRow | null> {
    const result = await this.db.query(
      `SELECT
          id::text,
          client_id::text,
          title,
          description,
          external_campaign_id,
          external_campaign_name,
          version,
          asset_url,
          asset_type,
          status,
          submitted_by,
          submitted_at,
          reviewed_by,
          reviewed_at,
          review_note,
          temporal_workflow_id
        FROM creative_submissions
        WHERE id = $1::uuid
        LIMIT 1`,
      [id],
    );
    const row = result.rows[0] as CreativeDbRow | undefined;
    return row ? this.mapRow(row) : null;
  }

  async updateDecision(
    id: string,
    status: 'approved' | 'rejected',
    reviewedBy: string,
    reviewNote: string | null,
  ): Promise<CreativeRow | null> {
    const result = await this.db.query(
      `UPDATE creative_submissions
       SET status = $2,
           reviewed_by = $3,
           reviewed_at = NOW(),
           review_note = $4,
           updated_at = NOW()
       WHERE id = $1::uuid AND status = 'pending_client'
       RETURNING
          id::text,
          client_id::text,
          title,
          description,
          external_campaign_id,
          external_campaign_name,
          version,
          asset_url,
          asset_type,
          status,
          submitted_by,
          submitted_at,
          reviewed_by,
          reviewed_at,
          review_note,
          temporal_workflow_id`,
      [id, status, reviewedBy, reviewNote],
    );
    const row = result.rows[0] as CreativeDbRow | undefined;
    return row ? this.mapRow(row) : null;
  }

  private mapRow(row: CreativeDbRow): CreativeRow {
    return {
      id: row.id,
      client_id: row.client_id,
      title: row.title,
      description: row.description,
      external_campaign_id: row.external_campaign_id,
      external_campaign_name: row.external_campaign_name,
      version: Number(row.version),
      asset_url: row.asset_url,
      asset_type: row.asset_type,
      status: row.status,
      submitted_by: row.submitted_by,
      submitted_at: this.toIso(row.submitted_at) ?? new Date().toISOString(),
      reviewed_by: row.reviewed_by,
      reviewed_at: row.reviewed_at ? this.toIso(row.reviewed_at) : null,
      review_note: row.review_note,
      temporal_workflow_id: row.temporal_workflow_id,
    };
  }

  private toIso(value: Date | string): string | null {
    if (value instanceof Date) {
      return value.toISOString();
    }
    return value ? String(value) : null;
  }
}
