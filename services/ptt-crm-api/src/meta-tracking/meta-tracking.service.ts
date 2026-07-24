import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { JobQueueRepository } from '../webhooks/job-queue.repository';
import { MetaTrackingRepository } from './meta-tracking.repository';
import {
  CapiEventsListResponse,
  CapiFlushResponse,
  CapiRetryResponse,
  TrackingHealthResponse,
} from './meta-tracking.types';
import {
  computeTrackingHealthGlobal,
  emptyTrackingHealthGlobal,
} from './tracking-health.util';

@Injectable()
export class MetaTrackingService {
  constructor(private readonly repo: MetaTrackingRepository) {}

  isTrackingEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  private async ensureCapiReady(): Promise<void> {
    if (!(await this.repo.pgCapiEventLogReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'capi_event_log_not_ready' });
    }
  }

  async getHealth(query: {
    client_id?: string;
    window_days?: string;
  }): Promise<TrackingHealthResponse> {
    if (!this.isTrackingEnabled()) {
      return {
        ok: true,
        disabled: true,
        window_days: 7,
        global: emptyTrackingHealthGlobal(),
        accounts: [],
        attribution_model: 'last_touch_crm',
      };
    }

    await this.ensureCapiReady();
    const windowDays = query.window_days ? Number(query.window_days) : 7;
    const days = Number.isFinite(windowDays) ? windowDays : 7;
    const clientId = query.client_id?.trim() || undefined;

    const [byStatus, avgLatencyMs, accounts] = await Promise.all([
      this.repo.countCapiByStatus(days, clientId),
      this.repo.avgCapiLatencyMs(days, clientId),
      this.repo.listTrackingAccounts(clientId),
    ]);

    return {
      ok: true,
      window_days: days,
      global: computeTrackingHealthGlobal({ byStatus, avgLatencyMs }),
      accounts,
      attribution_model: 'last_touch_crm',
    };
  }
}

@Injectable()
export class MetaCapiEventsService {
  constructor(
    private readonly repo: MetaTrackingRepository,
    private readonly jobQueue: JobQueueRepository,
  ) {}

  isTrackingEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  private async ensureCapiReady(): Promise<void> {
    if (!(await this.repo.pgCapiEventLogReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'capi_event_log_not_ready' });
    }
  }

  async listEvents(query: {
    client_id?: string;
    status?: string;
    event_name?: string;
    limit?: string;
    offset?: string;
  }): Promise<CapiEventsListResponse> {
    if (!this.isTrackingEnabled()) {
      return { ok: true, disabled: true, events: [], count: 0 };
    }

    await this.ensureCapiReady();
    const limit = query.limit ? Number(query.limit) : 50;
    const offset = query.offset ? Number(query.offset) : 0;
    const events = await this.repo.listCapiEvents({
      clientId: query.client_id?.trim() || undefined,
      status: query.status?.trim() || undefined,
      eventName: query.event_name?.trim() || undefined,
      limit: Number.isFinite(limit) ? limit : 50,
      offset: Number.isFinite(offset) ? offset : 0,
    });
    return { ok: true, events, count: events.length };
  }

  private isCapiDispatchAllowed(): boolean {
    const capiEnabled = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_CAPI_ENABLED ?? '0').trim().toLowerCase(),
    );
    const stubMode = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_CAPI_STUB ?? '0').trim().toLowerCase(),
    );
    return capiEnabled || stubMode;
  }

  private async enqueueCapiReplay(
    row: { id: string; client_id: string },
  ): Promise<CapiRetryResponse['job']> {
    if (!this.isCapiDispatchAllowed()) {
      return null;
    }
    const job = await this.jobQueue.enqueueCapiDispatch({
      payload: {
        capi_log_id: row.id,
        client_id: row.client_id,
        replay: true,
      },
      idempotencyKey: `capi:replay:${row.id}`,
      clientId: row.client_id,
    });
    if (!job) {
      return null;
    }
    return {
      id: job.id,
      job_type: job.job_type,
      status: job.status,
      created: job.created,
    };
  }

  async retryEvent(logId: string): Promise<CapiRetryResponse> {
    if (!this.isTrackingEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_tracking_disabled' });
    }

    await this.ensureCapiReady();
    const existing = await this.repo.getCapiEventById(logId.trim());
    if (!existing) {
      throw new NotFoundException({ error: 'Not found' });
    }
    if (!['failed', 'pending'].includes(existing.status)) {
      throw new BadRequestException({
        error: 'invalid_status',
        hint: 'Only failed or pending events can be retried',
        status: existing.status,
      });
    }

    const row = await this.repo.resetCapiEventPending(existing.id);
    if (!row) {
      throw new NotFoundException({ error: 'Not found' });
    }

    const job = await this.enqueueCapiReplay(row);
    return {
      ok: true,
      log_id: row.id,
      status: row.status,
      job,
      skipped: job == null,
      reason: job == null ? 'capi_dispatch_disabled_or_jobs_off' : undefined,
    };
  }

  async flushPending(query: {
    client_id?: string;
    limit?: string;
  }): Promise<CapiFlushResponse> {
    if (!this.isTrackingEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_tracking_disabled' });
    }

    await this.ensureCapiReady();
    const limit = query.limit ? Number(query.limit) : 50;
    const rows = await this.repo.listFlushableCapiEvents({
      clientId: query.client_id?.trim() || undefined,
      limit: Number.isFinite(limit) ? limit : 50,
    });

    const jobs: CapiFlushResponse['jobs'] = [];
    let enqueued = 0;
    let skipped = 0;

    for (const row of rows) {
      await this.repo.resetCapiEventPending(row.id);
      const job = await this.enqueueCapiReplay(row);
      if (job) {
        enqueued += 1;
        jobs.push({ log_id: row.id, job_id: job.id });
      } else {
        skipped += 1;
        jobs.push({ log_id: row.id, skipped: true, reason: 'capi_dispatch_disabled_or_jobs_off' });
      }
    }

    return {
      ok: true,
      processed: rows.length,
      enqueued,
      skipped,
      jobs,
    };
  }
}
