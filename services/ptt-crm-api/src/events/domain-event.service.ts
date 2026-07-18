import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { buildEventIdempotencyKey } from './event-idempotency';

export interface DomainEventPayload {
  [key: string]: unknown;
}

@Injectable()
export class DomainEventService implements OnModuleDestroy {
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

  async emit(
    eventType: string,
    aggregateType: string,
    aggregateId: string,
    payload: DomainEventPayload,
    correlationId?: string | null,
    idempotencyKey?: string | null,
  ): Promise<string | null> {
    const idem = idempotencyKey ?? buildEventIdempotencyKey(eventType, payload);
    if (idem) {
      const result = await this.db.query(
        `INSERT INTO domain_events (
           event_type, aggregate_type, aggregate_id, payload, correlation_id, idempotency_key
         )
         VALUES ($1, $2, $3, $4::jsonb, $5, $6)
         ON CONFLICT (idempotency_key) WHERE (idempotency_key IS NOT NULL) DO NOTHING
         RETURNING id::text`,
        [eventType, aggregateType, aggregateId, JSON.stringify(payload), correlationId ?? null, idem],
      );
      return (result.rows[0]?.id as string | undefined) ?? null;
    }
    const result = await this.db.query(
      `INSERT INTO domain_events (event_type, aggregate_type, aggregate_id, payload, correlation_id)
       VALUES ($1, $2, $3, $4::jsonb, $5)
       RETURNING id::text`,
      [eventType, aggregateType, aggregateId, JSON.stringify(payload), correlationId ?? null],
    );
    return (result.rows[0]?.id as string | undefined) ?? null;
  }
}
