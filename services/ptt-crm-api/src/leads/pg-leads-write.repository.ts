import { BadRequestException, Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool, PoolClient } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { pgRowToV1 } from './lead-v1.mapper';
import {
  CreateLeadV1Body,
  LeadV1,
  PatchLeadResult,
  PatchLeadV1Body,
  PgLeadRow,
} from './leads.types';

const STAGING_ID_MIN = 900_000_000;

@Injectable()
export class PgLeadsWriteRepository implements OnModuleDestroy {
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

  async createLead(body: CreateLeadV1Body): Promise<LeadV1> {
    if (this.config.leadsCreateIdMode === 'prod') {
      return this.createLeadProd(body);
    }
    return this.createLeadStaging(body);
  }

  async createLeadStaging(body: CreateLeadV1Body): Promise<LeadV1> {
    return this.insertLead(body, {
      leadId: (client) => this.nextStagingLeadId(client),
      writeSource: 'staging',
      meta: {
        staging_only: true,
        nest_write: true,
        created_via: 'POST /api/v1/leads',
      },
      defaultSource: 'staging',
    });
  }

  async createLeadProd(body: CreateLeadV1Body): Promise<LeadV1> {
    if (!body.client_id?.trim()) {
      throw new BadRequestException({ error: 'client_id is required for prod create' });
    }
    return this.insertLead(body, {
      leadId: async (client) => this.nextProdLeadId(client),
      writeSource: 'nest',
      meta: {
        nest_write: true,
        prod_create: true,
        created_via: 'POST /api/v1/leads',
      },
      defaultSource: body.source?.trim() || 'api',
    });
  }

  private async insertLead(
    body: CreateLeadV1Body,
    opts: {
      leadId: (client: PoolClient) => Promise<number>;
      writeSource: string;
      meta: Record<string, unknown>;
      defaultSource: string;
    },
  ): Promise<LeadV1> {
    const client = await this.db.connect();
    try {
      await client.query('BEGIN');
      const leadId = await opts.leadId(client);
      const now = new Date();
      await client.query(
        `INSERT INTO crm_leads (
           sqlite_lead_id, full_name, phone, email, status, source, owner_id,
           is_duplicate, meta_json, agency_client_id, channel, external_lead_id,
           campaign_id, received_at, created_at, updated_at, write_source, sync_version
         ) VALUES (
           $1, $2, $3, $4, $5, $6, $7,
           FALSE, $8::jsonb, $9::uuid, $10, $11,
           $12, $13::timestamptz, $13::timestamptz, $13::timestamptz, $14, 1
         )`,
        [
          leadId,
          body.full_name.trim(),
          body.phone ?? '',
          body.email ?? '',
          body.status?.trim() || 'new',
          body.source?.trim() || opts.defaultSource,
          body.owner_id ?? null,
          JSON.stringify(opts.meta),
          body.client_id ?? null,
          body.channel?.trim() || '',
          body.external_lead_id ?? null,
          body.campaign_id ?? null,
          now,
          opts.writeSource,
        ],
      );
      await client.query('COMMIT');
      const lead = await this.getLeadById(leadId);
      if (!lead) {
        throw new BadRequestException({ error: 'Create failed' });
      }
      return lead;
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  async patchLead(leadId: number, body: PatchLeadV1Body): Promise<PatchLeadResult | null> {
    const existing = await this.getLeadById(leadId);
    if (!existing) {
      return null;
    }

    const sets: string[] = [
      'synced_at = NOW()',
      'updated_at = NOW()',
      'write_source = \'nest\'',
      'sync_version = sync_version + 1',
    ];
    const params: unknown[] = [];
    let assigned = false;
    let scored = false;
    let statusChanged = false;
    const previousStatus = existing.status?.trim() || null;

    const push = (clause: string, value: unknown) => {
      params.push(value);
      sets.push(clause.replace('?', `$${params.length}`));
    };

    if (body.status !== undefined) {
      const nextStatus = body.status.trim();
      statusChanged = previousStatus !== nextStatus;
      push('status = ?', nextStatus);
    }
    if (body.owner_id !== undefined) {
      const prev = existing.owner_id;
      const next = body.owner_id;
      push('owner_id = ?', next);
      assigned = prev !== next && next != null;
    }
    if (body.score !== undefined) {
      scored = true;
      push(
        `meta_json = meta_json || ?::jsonb`,
        JSON.stringify({ score: body.score, score_stub: true, scored_at: new Date().toISOString() }),
      );
    }

    if (sets.length <= 2) {
      throw new BadRequestException({ error: 'No supported patch fields' });
    }

    params.push(leadId);
    await this.db.query(
      `UPDATE crm_leads SET ${sets.join(', ')} WHERE sqlite_lead_id = $${params.length}`,
      params,
    );

    const lead = await this.getLeadById(leadId);
    if (!lead) {
      throw new BadRequestException({ error: 'Patch failed' });
    }
    return { lead, assigned, scored, status_changed: statusChanged, previous_status: previousStatus };
  }

  private async nextStagingLeadId(client: PoolClient): Promise<number> {
    const result = await client.query(
      `SELECT COALESCE(MAX(sqlite_lead_id), $1 - 1) + 1 AS next_id
       FROM crm_leads WHERE sqlite_lead_id >= $1`,
      [STAGING_ID_MIN],
    );
    return Number(result.rows[0]?.next_id ?? STAGING_ID_MIN);
  }

  private async nextProdLeadId(client: PoolClient): Promise<number> {
    const result = await client.query(`SELECT nextval('crm_leads_prod_id_seq') AS next_id`);
    const id = Number(result.rows[0]?.next_id ?? 0);
    if (!Number.isFinite(id) || id <= 0 || id >= STAGING_ID_MIN) {
      throw new BadRequestException({
        error: 'prod_id_allocator_unavailable',
        hint: 'Apply ./scripts/apply_pg_ddl_v3_sprint0.sh',
      });
    }
    return id;
  }

  private async getLeadById(leadId: number): Promise<LeadV1 | null> {
    const result = await this.db.query(
      `SELECT l.sqlite_lead_id, l.full_name, l.phone, l.email, l.status, l.source,
              l.owner_id, l.is_duplicate, l.agency_client_id, l.channel,
              l.external_lead_id, l.campaign_id, l.received_at, l.created_at
       FROM crm_leads l WHERE l.sqlite_lead_id = $1`,
      [leadId],
    );
    const row = result.rows[0] as PgLeadRow | undefined;
    return row ? pgRowToV1(row) : null;
  }
}
