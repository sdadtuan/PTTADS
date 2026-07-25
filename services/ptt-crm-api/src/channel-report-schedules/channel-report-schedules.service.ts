import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { JobQueueRepository } from '../webhooks/job-queue.repository';
import { ChannelReportSchedulesRepository } from './channel-report-schedules.repository';
import {
  ChannelReportKind,
  ChannelReportScheduleListResponse,
  ChannelReportScheduleRow,
  CreateChannelReportScheduleBody,
  PatchChannelReportScheduleBody,
} from './channel-report-schedules.types';

@Injectable()
export class ChannelReportSchedulesJobService {
  constructor(
    private readonly config: AppConfigService,
    private readonly jobQueue: JobQueueRepository,
  ) {}

  private jobType(kind: ChannelReportKind): string {
    return kind === 'meta' ? 'meta_report_schedules' : 'zalo_report_schedules';
  }

  async enqueueRun(
    kind: ChannelReportKind,
    scheduleId: string,
    clientId: string,
  ): Promise<{ ok: boolean; job_id: string | null }> {
    if (!this.config.jobsEnabled) {
      return { ok: true, job_id: null };
    }
    const job = await this.jobQueue.enqueueAgencyJob({
      jobType: this.jobType(kind),
      payload: { schedule_id: scheduleId, client_id: clientId },
      idempotencyKey: `${this.jobType(kind)}:${scheduleId}:${Date.now()}`,
      clientId,
    });
    return { ok: true, job_id: job?.id ?? null };
  }

  async enqueueDue(kind: ChannelReportKind, asOf?: string): Promise<{ ok: boolean; job_id: string | null }> {
    if (!this.config.jobsEnabled) {
      return { ok: true, job_id: null };
    }
    const day = asOf?.trim() || new Date().toISOString().slice(0, 10);
    const job = await this.jobQueue.enqueueAgencyJob({
      jobType: this.jobType(kind),
      payload: { as_of: day },
      idempotencyKey: `${this.jobType(kind)}:due:${day}`,
      clientId: '00000000-0000-0000-0000-000000000000',
    });
    return { ok: true, job_id: job?.id ?? null };
  }
}

@Injectable()
export class ChannelReportSchedulesService {
  constructor(
    private readonly repo: ChannelReportSchedulesRepository,
    private readonly jobs: ChannelReportSchedulesJobService,
  ) {}

  private async ensureReady(kind: ChannelReportKind): Promise<void> {
    if (!(await this.repo.tableReady(kind))) {
      throw new ServiceUnavailableException({
        ok: false,
        error: `${kind}_report_schedules_table_not_ready`,
      });
    }
  }

  async list(
    kind: ChannelReportKind,
    clientId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<ChannelReportScheduleListResponse> {
    const ready = await this.repo.tableReady(kind);
    if (!ready) {
      return { ok: true, items: [], total: 0, limit: 50, offset: 0, table_ready: false };
    }
    const out = await this.repo.list({ kind, clientId, ...params });
    return { ok: true, ...out, table_ready: true };
  }

  async create(
    kind: ChannelReportKind,
    body: CreateChannelReportScheduleBody,
  ): Promise<ChannelReportScheduleRow> {
    await this.ensureReady(kind);
    const clientId = body.client_id?.trim();
    if (!clientId) {
      throw new ServiceUnavailableException({ error: 'client_id_required' });
    }
    return this.repo.create({
      kind,
      clientId,
      reportScope: body.report_scope,
      exportFormat: body.export_format,
      windowDays: body.window_days,
      cadence: body.cadence,
      dayOfWeek: body.day_of_week,
      dayOfMonth: body.day_of_month,
      recipientEmails: body.recipient_emails,
      ccEmails: body.cc_emails,
      bccEmails: body.bcc_emails,
      portalLinkEnabled: body.portal_link_enabled,
    });
  }

  async patch(
    kind: ChannelReportKind,
    id: string,
    body: PatchChannelReportScheduleBody,
  ): Promise<ChannelReportScheduleRow> {
    await this.ensureReady(kind);
    return this.repo.update(kind, id, body as Record<string, unknown>);
  }

  async delete(kind: ChannelReportKind, id: string): Promise<{ ok: boolean }> {
    await this.ensureReady(kind);
    return this.repo.delete(kind, id);
  }

  async run(kind: ChannelReportKind, id: string): Promise<{ ok: boolean; job_id: string | null }> {
    await this.ensureReady(kind);
    const row = await this.repo.get(kind, id);
    if (!row) {
      throw new ServiceUnavailableException({ error: 'schedule_not_found' });
    }
    return this.jobs.enqueueRun(kind, id, row.client_id);
  }

  async runDue(kind: ChannelReportKind, asOf?: string): Promise<{ ok: boolean; job_id: string | null }> {
    await this.ensureReady(kind);
    return this.jobs.enqueueDue(kind, asOf);
  }
}
