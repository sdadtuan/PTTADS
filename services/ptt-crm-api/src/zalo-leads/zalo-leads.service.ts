import { Injectable, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { AgencySideEffectsService } from '../agency/agency-side-effects.service';
import { ZaloLeadsRepository } from './zalo-leads.repository';
import type {
  ZaloFormPollResponse,
  ZaloFormsListResponse,
  ZaloLeadEventsResponse,
  ZaloLeadsListResponse,
} from './zalo-leads.types';

@Injectable()
export class ZaloLeadsService {
  constructor(
    private readonly repo: ZaloLeadsRepository,
    private readonly sideEffects: AgencySideEffectsService,
  ) {}

  private async ensureReady(): Promise<void> {
    if (!(await this.repo.tablesReady())) {
      throw new ServiceUnavailableException({
        error: 'zalo_leads_not_ready',
        hint: './scripts/apply_pg_ddl_zalo_leads.sh',
      });
    }
  }

  async listLeads(params: {
    client_id?: string;
    form_id?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }): Promise<ZaloLeadsListResponse> {
    await this.ensureReady();
    const { rows, total } = await this.repo.listLeads({
      clientId: params.client_id,
      formId: params.form_id,
      q: params.q,
      limit: params.limit,
      offset: params.offset,
    });
    return {
      ok: true,
      leads: rows,
      total,
      filters: {
        client_id: params.client_id ?? null,
        form_id: params.form_id ?? null,
        q: params.q ?? null,
      },
    };
  }

  async listForms(params: { client_id?: string }): Promise<ZaloFormsListResponse> {
    await this.ensureReady();
    const forms = await this.repo.listForms({ clientId: params.client_id });
    return { ok: true, forms };
  }

  async pollForm(formId: string, params: { client_id?: string; force?: boolean }): Promise<ZaloFormPollResponse> {
    await this.ensureReady();
    const ctx = await this.repo.resolveFormContext(formId, params.client_id);
    if (!ctx) {
      throw new NotFoundException({ error: 'form_not_found', form_id: formId });
    }
    const jobs = await this.sideEffects.enqueueZaloFormLeadPoll({
      clientId: ctx.client_id,
      formId: ctx.form_id,
      oaId: ctx.oa_id,
      force: Boolean(params.force),
    });
    if (!jobs.length) {
      throw new ServiceUnavailableException({
        error: 'jobs_disabled',
        hint: 'Bật PTT_JOBS_ENABLED=1 và chạy ptt-worker',
      });
    }
    return {
      ok: true,
      jobs_enqueued: jobs.map((j) => ({
        id: j.id,
        job_type: j.job_type,
        status: j.status,
        created: j.created,
      })),
    };
  }

  async leadEvents(leadId: string): Promise<ZaloLeadEventsResponse> {
    await this.ensureReady();
    const events = await this.repo.listLeadEvents(leadId);
    return { ok: true, lead_id: leadId, events };
  }
}
