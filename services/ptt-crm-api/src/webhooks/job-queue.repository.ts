import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import type { NormalizedLeadPayload } from './webhook-lead.types';

export interface EnqueuedJob {
  id: string;
  job_type: string;
  status: string;
  idempotency_key: string;
  correlation_id: string | null;
  created: boolean;
}

export interface EnqueueIngestResult {
  mode: 'queue' | 'none';
  jobs: EnqueuedJob[];
}

@Injectable()
export class JobQueueRepository implements OnModuleDestroy {
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

  async enqueueIngestLeads(
    leads: NormalizedLeadPayload[],
    opts: { channel: string; correlationId?: string; clientId?: string },
  ): Promise<EnqueueIngestResult> {
    if (!leads.length) {
      return { mode: 'none', jobs: [] };
    }
    if (!this.config.jobsEnabled || !this.config.webhookEnqueueEnabled) {
      throw new Error('Job queue disabled (PTT_JOBS_ENABLED or PTT_WEBHOOK_V1_ENQUEUE=0)');
    }

    const jobs: EnqueuedJob[] = [];
    for (const lead of leads) {
      const channel = opts.channel;
      const extId = String(lead.external_lead_id ?? lead.idempotency_key ?? '');
      const idem = String(lead.idempotency_key || `ingest:${channel}:${extId}`);
      const payload = {
        lead,
        channel,
        client_id: opts.clientId || lead.client_id || '',
      };
      const clientId = this.normalizeClientUuid(opts.clientId || lead.client_id);
      jobs.push(
        await this.enqueueJobRecord({
          jobType: 'ingest_lead',
          payload,
          idempotencyKey: idem,
          correlationId: opts.correlationId,
          clientId,
        }),
      );
    }
    return { mode: 'queue', jobs };
  }

  private normalizeClientUuid(clientId: string | undefined): string | null {
    const text = String(clientId ?? '').trim();
    if (!text || text === 'unknown') return null;
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(text)) {
      return text.toLowerCase();
    }
    return null;
  }

  private async enqueueJobRecord(input: {
    jobType: string;
    payload: Record<string, unknown>;
    idempotencyKey: string;
    correlationId?: string;
    clientId: string | null;
  }): Promise<EnqueuedJob> {
    const insert = await this.db.query(
      `INSERT INTO job_queue (
         job_type, payload, idempotency_key, correlation_id, client_id, max_attempts, status
       ) VALUES ($1, $2::jsonb, $3, $4, $5::uuid, 5, 'pending')
       ON CONFLICT (idempotency_key) DO NOTHING
       RETURNING id, job_type, status, idempotency_key, correlation_id`,
      [
        input.jobType,
        JSON.stringify(input.payload),
        input.idempotencyKey,
        input.correlationId ?? null,
        input.clientId,
      ],
    );
    if (insert.rows[0]) {
      const row = insert.rows[0] as {
        id: string;
        job_type: string;
        status: string;
        idempotency_key: string;
        correlation_id: string | null;
      };
      return {
        id: String(row.id),
        job_type: row.job_type,
        status: row.status,
        idempotency_key: row.idempotency_key,
        correlation_id: row.correlation_id,
        created: true,
      };
    }
    const existing = await this.db.query(
      `SELECT id, job_type, status, idempotency_key, correlation_id
       FROM job_queue WHERE idempotency_key = $1`,
      [input.idempotencyKey],
    );
    const row = existing.rows[0] as {
      id: string;
      job_type: string;
      status: string;
      idempotency_key: string;
      correlation_id: string | null;
    };
    return {
      id: String(row.id),
      job_type: row.job_type,
      status: row.status,
      idempotency_key: row.idempotency_key,
      correlation_id: row.correlation_id,
      created: false,
    };
  }

  async enqueueEmailJob(input: {
    jobType: string;
    payload: Record<string, unknown>;
    idempotencyKey: string;
    correlationId?: string;
    clientId: string;
  }): Promise<EnqueuedJob> {
    if (!this.config.jobsEnabled || !this.config.webhookEnqueueEnabled) {
      throw new Error('Job queue disabled (PTT_JOBS_ENABLED or PTT_WEBHOOK_V1_ENQUEUE=0)');
    }
    return this.enqueueJobRecord({
      jobType: input.jobType,
      payload: input.payload,
      idempotencyKey: input.idempotencyKey,
      correlationId: input.correlationId,
      clientId: this.normalizeClientUuid(input.clientId),
    });
  }

  /** Agency ops jobs (activate, token connect, manual sync) — only requires PTT_JOBS_ENABLED. */
  async enqueueAgencyJob(input: {
    jobType: string;
    payload: Record<string, unknown>;
    idempotencyKey: string;
    clientId: string;
    correlationId?: string;
  }): Promise<EnqueuedJob | null> {
    if (!this.config.jobsEnabled) {
      return null;
    }
    return this.enqueueJobRecord({
      jobType: input.jobType,
      payload: input.payload,
      idempotencyKey: input.idempotencyKey,
      correlationId: input.correlationId,
      clientId: this.normalizeClientUuid(input.clientId),
    });
  }

  /** B9 CAPI replay/retry — only requires PTT_JOBS_ENABLED. */
  async enqueueCapiDispatch(input: {
    payload: Record<string, unknown>;
    idempotencyKey: string;
    clientId: string;
    correlationId?: string;
  }): Promise<EnqueuedJob | null> {
    if (!this.config.jobsEnabled) {
      return null;
    }
    return this.enqueueJobRecord({
      jobType: 'capi_dispatch',
      payload: input.payload,
      idempotencyKey: input.idempotencyKey,
      correlationId: input.correlationId,
      clientId: this.normalizeClientUuid(input.clientId),
    });
  }

  async cancelPendingJobsForClient(clientId: string): Promise<number> {
    if (!this.config.jobsEnabled) {
      return 0;
    }
    const normalized = this.normalizeClientUuid(clientId);
    if (!normalized) {
      return 0;
    }
    const result = await this.db.query(
      `UPDATE job_queue
       SET status = 'dead',
           last_error = 'cancelled:client_offboarded',
           finished_at = NOW(),
           updated_at = NOW()
       WHERE client_id = $1::uuid
         AND status = 'pending'`,
      [normalized],
    );
    return result.rowCount ?? 0;
  }
}
