import { Injectable, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { AgencyService } from '../agency/agency.service';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';

@Injectable()
export class LifecycleOnboardingService {
  constructor(
    private readonly sqlite: ServiceLifecycleSqliteRepository,
    private readonly agency: AgencyService,
  ) {}

  async onboardingBrief(lifecycleId: number) {
    const ctx = this.sqlite.getLifecycleContext(lifecycleId);
    if (!ctx) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }

    const clientId = String(ctx.contract.agency_client_id ?? '').trim();
    if (!clientId) {
      return {
        lifecycle_id: lifecycleId,
        has_context: false,
        client_id: null,
        progress: { total: 0, completed: 0, percent: 0 },
        items: [] as Array<{ item_key: string; label: string; completed: boolean }>,
        workflow: null,
        client_status: null,
        client_name: null,
        links: {
          agency_checklist: null,
        },
        gate: {
          ok: true,
          warn_only: true,
          messages: ['HĐ chưa liên kết agency client — gán agency_client_id trên hợp đồng trước.'],
        },
        message: 'HĐ chưa có agency_client_id — liên kết client trước khi onboard.',
      };
    }

    let summary;
    try {
      summary = await this.agency.getOnboardingSummary(clientId);
    } catch (err) {
      if (err instanceof ServiceUnavailableException) {
        return {
          lifecycle_id: lifecycleId,
          has_context: true,
          client_id: clientId,
          progress: { total: 0, completed: 0, percent: 0 },
          items: [],
          workflow: null,
          client_status: null,
          client_name: null,
          links: {
            agency_checklist: `/agency/clients/${encodeURIComponent(clientId)}?tab=checklist`,
          },
          gate: { ok: true, warn_only: true, messages: ['PostgreSQL agency chưa sẵn sàng — checklist tạm ẩn.'] },
          message: 'PostgreSQL agency chưa sẵn sàng.',
        };
      }
      throw err;
    }

    const incomplete = summary.items.filter((i) => !i.completed).slice(0, 5);
    const onOnboardStage = ctx.stage === 'onboard';
    const gateMessages: string[] = [];
    if (onOnboardStage && summary.progress.percent < 100 && summary.client_status !== 'active') {
      gateMessages.push(
        `Checklist client ${summary.progress.completed}/${summary.progress.total} (${summary.progress.percent}%) — hoàn thiện trước khi Deliver.`,
      );
    }
    if (summary.client_status === 'active') {
      gateMessages.push('Agency client đã active — checklist coi như pass.');
    }

    return {
      lifecycle_id: lifecycleId,
      has_context: true,
      client_id: clientId,
      client_code: summary.client_code,
      client_name: summary.client_name,
      client_status: summary.client_status,
      progress: summary.progress,
      items: summary.items.map((i) => ({
        item_key: i.item_key,
        label: i.label,
        completed: i.completed,
        note: i.note,
      })),
      incomplete_preview: incomplete.map((i) => i.label),
      workflow: summary.workflow,
      strict_onboarding: summary.strict_onboarding,
      links: {
        agency_checklist: `/agency/clients/${encodeURIComponent(clientId)}?tab=checklist`,
        service_delivery: ctx.links.service_delivery,
      },
      gate: {
        ok: summary.client_status === 'active' || summary.progress.percent >= 100,
        warn_only: true,
        progress_percent: summary.progress.percent,
        messages: gateMessages.length
          ? gateMessages
          : ['Checklist client đạt yêu cầu cho giai đoạn Onboard.'],
      },
      message: null,
    };
  }
}
