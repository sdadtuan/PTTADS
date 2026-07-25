import { Injectable, NotFoundException } from '@nestjs/common';
import { AgencyRepository } from './agency.repository';
import { AgencyService } from './agency.service';
import { OnboardingOrchestratorRepository } from './onboarding-orchestrator.repository';
import {
  OnboardOrchestratorProgress,
  OnboardOrchestratorResponse,
  OnboardOrchestratorSignals,
  OnboardOrchestratorStep,
  OnboardOrchestratorStepDef,
  OnboardOrchestratorSyncResponse,
} from './onboarding-orchestrator.types';
import { PortalClientUsersRepository } from './portal-client-users.repository';

const ORCHESTRATOR_STEP_DEFS: OnboardOrchestratorStepDef[] = [
  {
    key: 'crm_lifecycle',
    label: 'Lifecycle stage Onboard',
    module: 'crm',
    sort_order: 1,
    href: ({ lifecycleUrl }) => lifecycleUrl,
    detect: (s) => {
      const onboard = s.linkedLifecycles.some((l) => l.stage === 'onboard');
      const anyLinked = s.linkedLifecycles.length > 0;
      return {
        done: onboard || anyLinked,
        detail: onboard
          ? `${s.linkedLifecycles.filter((l) => l.stage === 'onboard').length} lifecycle ở Onboard`
          : anyLinked
            ? `${s.linkedLifecycles.length} lifecycle liên kết`
            : 'Chưa liên kết lifecycle',
      };
    },
  },
  {
    key: 'agency_checklist',
    label: 'Checklist agency (legal, billing, brief…)',
    module: 'agency',
    sort_order: 2,
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=checklist`,
    detect: (s) => ({
      done: s.checklistProgress.percent >= 100,
      detail: `${s.checklistProgress.completed}/${s.checklistProgress.total} mục (${s.checklistProgress.percent}%)`,
    }),
  },
  {
    key: 'meta_ad_account',
    label: 'Meta ad account access',
    module: 'meta',
    sort_order: 3,
    checklist_item_key: 'ad_account_access',
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=channels`,
    detect: (s) => {
      const hasMeta = s.metaAccounts.length > 0;
      const checklist = s.checklistItems.find((i) => i.item_key === 'ad_account_access')?.completed;
      return {
        done: hasMeta || Boolean(checklist),
        detail: hasMeta ? `${s.metaAccounts.length} Meta account` : checklist ? 'Checklist ticked' : 'Chưa có Meta account',
      };
    },
  },
  {
    key: 'meta_token',
    label: 'Meta token / OAuth',
    module: 'meta',
    sort_order: 4,
    checklist_item_key: 'bm_access',
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=channels`,
    detect: (s) => {
      const withToken = s.metaAccounts.filter((a) => a.has_token && a.token_status !== 'expired');
      const checklist = s.checklistItems.find((i) => i.item_key === 'bm_access')?.completed;
      return {
        done: withToken.length > 0 || Boolean(checklist),
        detail:
          withToken.length > 0
            ? `${withToken.length} account có token hợp lệ`
            : checklist
              ? 'Checklist ticked'
              : 'Chưa lưu token Meta',
      };
    },
  },
  {
    key: 'meta_pixel',
    label: 'Pixel / dataset',
    module: 'meta',
    sort_order: 5,
    checklist_item_key: 'pixel_dataset',
    href: ({ clientId }) => `/meta/tracking?client_id=${encodeURIComponent(clientId)}`,
    detect: (s) => {
      const withPixel = s.metaAccounts.filter((a) => Boolean(a.pixel_id));
      const checklist = s.checklistItems.find((i) => i.item_key === 'pixel_dataset')?.completed;
      return {
        done: withPixel.length > 0 || Boolean(checklist),
        detail: withPixel.length > 0 ? 'Pixel ID đã cấu hình' : checklist ? 'Checklist ticked' : 'Chưa có pixel',
      };
    },
  },
  {
    key: 'meta_tracking',
    label: 'Tracking preflight OK',
    module: 'meta',
    sort_order: 6,
    href: ({ clientId }) => `/meta/tracking?client_id=${encodeURIComponent(clientId)}`,
    detect: (s) => {
      const ready = s.metaAccounts.some(
        (a) => a.has_token && a.token_status !== 'expired' && Boolean(a.pixel_id),
      );
      return {
        done: ready,
        detail: ready ? 'Token + pixel sẵn sàng preflight' : 'Cần token và pixel trước khi preflight',
      };
    },
  },
  {
    key: 'zalo_account',
    label: 'Zalo OA / ad account',
    module: 'zalo',
    sort_order: 15,
    optional: true,
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=channels`,
    detect: (s) => ({
      done: s.zaloAccounts.length > 0,
      detail: s.zaloAccounts.length > 0 ? `${s.zaloAccounts.length} Zalo account` : 'Chưa có Zalo account',
    }),
  },
  {
    key: 'zalo_token',
    label: 'Zalo OAuth token',
    module: 'zalo',
    sort_order: 16,
    optional: true,
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=channels`,
    detect: (s) => {
      const withToken = s.zaloAccounts.filter((a) => a.has_token && a.token_status !== 'expired');
      return {
        done: withToken.length > 0,
        detail: withToken.length > 0 ? `${withToken.length} account có token hợp lệ` : 'Chưa connect OAuth Zalo',
      };
    },
  },
  {
    key: 'zalo_form',
    label: 'Lead form IDs configured',
    module: 'zalo',
    sort_order: 17,
    optional: true,
    href: ({ clientId }) => `/zalo/leads?client_id=${encodeURIComponent(clientId)}`,
    detect: (s) => ({
      done: s.zaloFormConfigured,
      detail: s.zaloFormConfigured ? 'Form IDs đã cấu hình' : 'Chưa cấu hình form IDs trên channel Zalo',
    }),
  },
  {
    key: 'zalo_sync',
    label: 'Zalo insights sync OK',
    module: 'zalo',
    sort_order: 18,
    optional: true,
    href: ({ clientId }) => `/zalo/zalo-ads?client_id=${encodeURIComponent(clientId)}`,
    detect: (s) => ({
      done: s.zaloSyncOk,
      detail: s.zaloSyncOk ? 'Có dữ liệu daily_performance channel=zalo' : 'Chưa sync insights Zalo',
    }),
  },
  {
    key: 'zalo_first_lead',
    label: 'First Zalo lead in CRM',
    module: 'zalo',
    sort_order: 19,
    optional: true,
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=leads`,
    detect: (s) => ({
      done: s.zaloLeadCount > 0,
      detail: s.zaloLeadCount > 0 ? `${s.zaloLeadCount} lead Zalo` : 'Chưa có lead Zalo trong CRM',
    }),
  },
  {
    key: 'seo_workspace',
    label: 'SEO workspace + GSC OAuth',
    module: 'seo',
    sort_order: 7,
    optional: true,
    href: ({ seoCustomerId }) =>
      seoCustomerId != null ? `/seo/clients/${seoCustomerId}` : '/seo/clients',
    detect: (s) => ({
      done: s.seo.mapped && (s.seo.gsc_connected || s.seo.has_settings),
      detail: !s.seo.mapped
        ? 'Chưa map SEO client — bỏ qua nếu không có HĐ SEO'
        : s.seo.gsc_connected
          ? 'GSC OAuth connected'
          : s.seo.has_settings
            ? 'Workspace có domain — chưa OAuth GSC'
            : 'Chưa cấu hình SEO workspace',
    }),
  },
  {
    key: 'email_workspace',
    label: 'Email workspace',
    module: 'email',
    sort_order: 8,
    optional: true,
    href: ({ clientId }) => `/email/clients/${encodeURIComponent(clientId)}`,
    detect: (s) => ({
      done: s.email.workspace,
      detail: s.email.workspace ? 'Workspace active' : 'Chưa tạo workspace — bỏ qua nếu không có HĐ Email',
    }),
  },
  {
    key: 'email_domain',
    label: 'Domain DNS verified',
    module: 'email',
    sort_order: 9,
    optional: true,
    href: ({ clientId }) => `/email/deliverability?client_id=${encodeURIComponent(clientId)}`,
    detect: (s) => ({
      done: s.email.verified_domain,
      detail: s.email.verified_domain ? 'Domain SPF pass' : 'Chưa verify domain',
    }),
  },
  {
    key: 'portal_users',
    label: 'Portal users',
    module: 'portal',
    sort_order: 10,
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=portal`,
    detect: (s) => {
      const active = s.portalUsers.filter((u) => u.active);
      return {
        done: active.length > 0,
        detail: active.length > 0 ? `${active.length} user active` : 'Chưa tạo portal user',
      };
    },
  },
  {
    key: 'client_approver',
    label: 'Client approver contact',
    module: 'portal',
    sort_order: 11,
    checklist_item_key: 'client_approver',
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=portal`,
    detect: (s) => {
      const approvers = s.portalUsers.filter((u) => u.active && u.role === 'approver');
      const checklist = s.checklistItems.find((i) => i.item_key === 'client_approver')?.completed;
      return {
        done: approvers.length > 0 || Boolean(checklist),
        detail: approvers.length > 0 ? `${approvers.length} approver` : checklist ? 'Checklist ticked' : 'Chưa có approver',
      };
    },
  },
  {
    key: 'hub_contract',
    label: 'Hub contract / lifecycle link',
    module: 'agency',
    sort_order: 12,
    checklist_item_key: 'hub_contract',
    href: ({ lifecycleUrl, clientId }) =>
      lifecycleUrl ?? `/agency/clients/${encodeURIComponent(clientId)}?tab=contracts`,
    detect: (s) => {
      const linked = s.linkedLifecycles.length > 0;
      const checklist = s.checklistItems.find((i) => i.item_key === 'hub_contract')?.completed;
      return {
        done: linked || Boolean(checklist),
        detail: linked ? `${s.linkedLifecycles.length} lifecycle liên kết` : checklist ? 'Checklist ticked' : 'Chưa link HĐ',
      };
    },
  },
  {
    key: 'webhook_test',
    label: 'Webhook test lead OK',
    module: 'agency',
    sort_order: 13,
    checklist_item_key: 'webhook_test',
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=leads`,
    detect: (s) => {
      const checklist = s.checklistItems.find((i) => i.item_key === 'webhook_test')?.completed;
      return {
        done: s.leadCount > 0 || Boolean(checklist),
        detail: s.leadCount > 0 ? `${s.leadCount} lead trong CRM` : checklist ? 'Checklist ticked' : 'Chưa có lead test',
      };
    },
  },
  {
    key: 'activate_client',
    label: 'Activate client',
    module: 'agency',
    sort_order: 20,
    manual_only: true,
    href: ({ clientId }) => `/agency/clients/${encodeURIComponent(clientId)}?tab=onboard`,
    detect: (s) => ({
      done: s.clientStatus === 'active',
      detail: s.clientStatus === 'active' ? 'Client active' : `Status: ${s.clientStatus}`,
    }),
  },
];

function progressFromSteps(steps: OnboardOrchestratorStep[]): OnboardOrchestratorProgress {
  const required = steps.filter((s) => s.status !== 'optional' && s.status !== 'skipped');
  const completed = required.filter((s) => s.status === 'done').length;
  const total = required.length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const allCompleted = steps.filter((s) => s.status === 'done').length;
  return {
    total: steps.length,
    completed: allCompleted,
    percent: steps.length ? Math.round((allCompleted / steps.length) * 100) : 0,
    required_total: total,
    required_completed: completed,
    required_percent: percent,
  };
}

function checklistProgress(items: Array<{ completed: boolean }>): OnboardOrchestratorProgress {
  const total = items.length;
  const completed = items.filter((i) => i.completed).length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  return { total, completed, percent, required_total: total, required_completed: completed, required_percent: percent };
}

@Injectable()
export class OnboardingOrchestratorService {
  constructor(
    private readonly agency: AgencyService,
    private readonly repo: AgencyRepository,
    private readonly detectRepo: OnboardingOrchestratorRepository,
    private readonly portalUsers: PortalClientUsersRepository,
  ) {}

  async getOrchestrator(clientId: string): Promise<OnboardOrchestratorResponse> {
    const signals = await this.collectSignals(clientId);
    return this.buildResponse(clientId, signals, null);
  }

  async syncOrchestrator(clientId: string): Promise<OnboardOrchestratorSyncResponse> {
    const signals = await this.collectSignals(clientId);
    const syncedItems: string[] = [];

    for (const def of ORCHESTRATOR_STEP_DEFS) {
      if (!def.checklist_item_key) continue;
      const item = signals.checklistItems.find((i) => i.item_key === def.checklist_item_key);
      if (!item || item.completed) continue;
      const { done } = def.detect(signals);
      if (!done) continue;
      try {
        await this.agency.patchOnboardingItem(clientId, def.checklist_item_key, {
          completed: true,
          completed_by: 'orchestrator:auto',
          note: 'Auto-detected by onboard orchestrator',
        });
        syncedItems.push(def.checklist_item_key);
        item.completed = true;
      } catch {
        // skip failed auto-tick
      }
    }

    if (syncedItems.length) {
      signals.checklistItems = (await this.repo.listOnboardingItems(clientId)).map((i) => ({
        item_key: i.item_key,
        label: i.label,
        completed: i.completed,
      }));
      signals.checklistProgress = checklistProgress(signals.checklistItems);
    }

    const orchestrator = this.buildResponse(clientId, signals, new Date().toISOString());
    return { client_id: clientId, synced_items: syncedItems, orchestrator };
  }

  private async collectSignals(clientId: string): Promise<
    OnboardOrchestratorSignals & {
      clientCode: string;
      clientName: string;
    }
  > {
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }

    const summary = await this.agency.getOnboardingSummary(clientId);
    const checklistItems = summary.items.map((i) => ({
      item_key: i.item_key,
      label: i.label,
      completed: i.completed,
    }));

    const metaAccounts = (client.channel_accounts ?? [])
      .filter((a) => a.channel === 'meta')
      .map((a) => ({
        has_token: Boolean(a.has_token),
        token_status: a.token_status ?? null,
        pixel_id: a.pixel_id ?? null,
      }));

    const zaloAccounts = (client.channel_accounts ?? [])
      .filter((a) => a.channel === 'zalo')
      .map((a) => ({
        has_token: Boolean(a.has_token),
        token_status: a.token_status ?? null,
        form_ids: Array.isArray(a.form_ids) ? a.form_ids.filter(Boolean) : [],
      }));

    const portalReady = await this.portalUsers.tableReady();
    const portalUsers = portalReady
      ? (await this.portalUsers.listByClient(clientId)).map((u) => ({ role: u.role, active: u.active }))
      : [];

    const [seo, email, leadCount, zaloLeadCount, zaloSyncOk] = await Promise.all([
      this.detectRepo.detectSeo(clientId),
      this.detectRepo.detectEmail(clientId),
      this.detectRepo.countLeads(clientId),
      this.detectRepo.countZaloLeads(clientId),
      this.detectRepo.zaloInsightsSynced(clientId),
    ]);

    const zaloFormConfigured = zaloAccounts.some((a) => a.form_ids.length > 0);

    return {
      clientCode: summary.client_code,
      clientName: summary.client_name,
      linkedLifecycles: summary.linked_lifecycles.map((l) => ({
        lifecycle_id: l.lifecycle_id,
        stage: l.stage,
        service_delivery_url: l.service_delivery_url,
      })),
      checklistItems,
      checklistProgress: checklistProgress(checklistItems),
      clientStatus: client.status,
      metaAccounts,
      zaloAccounts,
      zaloLeadCount,
      zaloFormConfigured,
      zaloSyncOk,
      portalUsers,
      seo,
      email,
      leadCount,
    };
  }

  private buildResponse(
    clientId: string,
    signals: OnboardOrchestratorSignals & { clientCode: string; clientName: string },
    syncedAt: string | null,
  ): OnboardOrchestratorResponse {
    const lifecycleOnboard = signals.linkedLifecycles.find((l) => l.stage === 'onboard');
    const lifecycleUrl =
      lifecycleOnboard?.service_delivery_url ??
      signals.linkedLifecycles[0]?.service_delivery_url ??
      null;
    const seoCustomerId = signals.seo.customer_id;

    const hrefCtx = { clientId, seoCustomerId, lifecycleUrl };

    const steps: OnboardOrchestratorStep[] = ORCHESTRATOR_STEP_DEFS.map((def) => {
      const { done, detail } = def.detect(signals);
      const checklistDone = def.checklist_item_key
        ? signals.checklistItems.find((i) => i.item_key === def.checklist_item_key)?.completed
        : false;
      const autoDetected = done && !checklistDone && !def.manual_only;
      let status: OnboardOrchestratorStep['status'] = done ? 'done' : 'pending';
      if (def.optional && !done && (def.key === 'seo_workspace' ? !signals.seo.mapped : def.key.startsWith('email'))) {
        if (def.key === 'seo_workspace' && !signals.seo.mapped) {
          status = 'optional';
        } else if (def.key.startsWith('email') && !signals.email.workspace && def.key === 'email_domain') {
          status = 'optional';
        } else if (def.key === 'email_workspace' && !signals.email.workspace) {
          status = 'optional';
        }
      }
      if (def.optional && def.module === 'zalo' && signals.zaloAccounts.length === 0) {
        status = 'optional';
      }

      return {
        key: def.key,
        label: def.label,
        module: def.module,
        sort_order: def.sort_order,
        status,
        href: def.href ? def.href(hrefCtx) : null,
        auto_detected: autoDetected,
        manual_only: Boolean(def.manual_only),
        optional: Boolean(def.optional),
        checklist_item_key: def.checklist_item_key ?? null,
        hint: def.optional ? 'Bỏ qua nếu không có trong HĐ' : null,
        detection_detail: detail,
      };
    });

    return {
      client_id: clientId,
      client_code: signals.clientCode,
      client_name: signals.clientName,
      client_status: signals.clientStatus,
      steps,
      progress: progressFromSteps(steps),
      checklist_progress: signals.checklistProgress,
      linked_lifecycle_url: lifecycleUrl ? `${lifecycleUrl}?tab=onboard` : null,
      synced_at: syncedAt,
    };
  }
}

export { ORCHESTRATOR_STEP_DEFS, progressFromSteps, checklistProgress };
