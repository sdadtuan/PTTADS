import { BadRequestException, Injectable, Logger, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import * as fs from 'fs';
import * as path from 'path';
import { AgencySideEffectsService } from './agency-side-effects.service';
import { AgencyRepository } from './agency.repository';
import {
  AgencyClientsListResponse,
  AgencyClientDetail,
  AgencySideEffectsSummary,
  AgencyStatsResponse,
  FacebookHubResponse,
  FacebookHubAlert,
  HubCampaignMapsResponse,
  HubCampaignGlobalRow,
  HubCampaignMapRow,
  JobsListResponse,
  NotificationsListResponse,
  OnboardingResponse,
  OnboardingSummaryResponse,
  OnboardingWorkflowSnapshot,
  KpiDefinitionRow,
  AddChannelAccountBody,
  UpdateChannelAccountBody,
  UpdateClientBody,
  PatchHubCampaignMapBody,
  CreateHubCampaignMapBody,
  UpdateHubCampaignMapBody,
  SetChannelTokenBody,
  CreateKpiDefinitionBody,
  UpdateKpiDefinitionBody,
  ClientLeadRow,
} from './agency.types';
import { TokenVaultError } from './token-vault.util';
import {
  buildFacebookHubCampaignsCsv,
  buildFacebookHubClientsCsv,
  facebookHubExportFilename,
  normalizeHubClientUuid,
} from './facebook-hub.util';
import {
  checkAutosyncStandalone,
  evaluateSoakGate,
  ManualUatState,
  readMigrationSignoff,
  writeManualUat,
} from './meta-migration.util';
import { WorkflowsService } from '../workflows/workflows.service';
import { LeadsContractSqliteRepository } from '../leads-contract/leads-contract-sqlite.repository';

const META_CAMPAIGN_ID_RE = /^[0-9]{5,20}$/;
const VALID_HUB_CHANNELS = new Set(['meta', 'zalo', 'google']);
const VALID_CHANNELS = new Set(['meta', 'zalo', 'google', 'email']);
const VALID_CHANNEL_STATUSES = new Set(['active', 'inactive', 'revoked', 'error']);

function strictOnboardingEnabled(): boolean {
  const raw = (process.env.PTT_CLIENT_STRICT_ONBOARDING ?? '1').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

function normalizeMetaCampaignId(raw: string): string {
  return raw.replace(/\D/g, '').trim();
}

function normalizeExternalCampaignId(channel: string, raw: string): string {
  const ch = channel.trim().toLowerCase();
  if (ch === 'meta') return normalizeMetaCampaignId(raw);
  return raw.trim();
}

function validateExternalCampaignId(channel: string, externalId: string): void {
  const ch = channel.trim().toLowerCase();
  if (ch === 'meta') {
    if (!META_CAMPAIGN_ID_RE.test(externalId)) {
      throw new BadRequestException({ error: 'invalid_meta_campaign_id' });
    }
    return;
  }
  if (!externalId || externalId.length > 128) {
    throw new BadRequestException({ error: 'invalid_external_campaign_id' });
  }
}

@Injectable()
export class AgencyService {
  private readonly logger = new Logger(AgencyService.name);

  constructor(
    private readonly repo: AgencyRepository,
    private readonly sideEffects: AgencySideEffectsService,
    private readonly workflows: WorkflowsService,
    private readonly contractSqlite: LeadsContractSqliteRepository,
  ) {}

  private async ensurePg(): Promise<void> {
    if (!(await this.repo.pgReady())) {
      throw new ServiceUnavailableException({
        error: 'pg_not_ready',
        hint: 'Kiểm tra DATABASE_URL và DDL agency',
      });
    }
  }

  async stats(): Promise<AgencyStatsResponse> {
    const pgReady = await this.repo.pgReady();
    if (!pgReady) {
      return { pg_ready: false, clients: {}, jobs: {} };
    }
    const [clients, jobs] = await Promise.all([this.repo.clientCounts(), this.repo.jobStats()]);
    return { pg_ready: true, clients, jobs };
  }

  async listClients(query: {
    status?: string;
    q?: string;
    owner_am_id?: string;
    industry?: string;
    limit?: number;
    offset?: number;
  }): Promise<AgencyClientsListResponse> {
    await this.ensurePg();
    const clients = await this.repo.listClients({
      status: query.status?.trim() || undefined,
      q: query.q?.trim() || undefined,
      ownerAmId: query.owner_am_id?.trim() || undefined,
      industrySlug: query.industry?.trim() || undefined,
      limit: Math.min(Math.max(query.limit ?? 100, 1), 200),
      offset: Math.max(query.offset ?? 0, 0),
    });
    return { clients };
  }

  async getClient(clientId: string): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return client;
  }

  async createClient(body: {
    code: string;
    name: string;
    industry_slug?: string;
    owner_am_id?: string;
    notes?: string;
  }): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const code = body.code?.trim() ?? '';
    const name = body.name?.trim() ?? '';
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{1,30}$/.test(code)) {
      throw new BadRequestException({ error: 'invalid_code' });
    }
    if (!name) {
      throw new BadRequestException({ error: 'name_required' });
    }
    const row = await this.repo.createClient({
      code,
      name,
      industry_slug: body.industry_slug,
      owner_am_id: body.owner_am_id,
      notes: body.notes,
    });
    await this.sideEffects.onClientCreated(row.id, body.owner_am_id);
    return { ...row, channel_accounts: [] };
  }

  async listJobs(query: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<JobsListResponse> {
    await this.ensurePg();
    const [stats, jobs] = await Promise.all([
      this.repo.jobStats(),
      this.repo.listJobs({
        status: query.status?.trim() || undefined,
        limit: Math.min(Math.max(query.limit ?? 50, 1), 200),
        offset: Math.max(query.offset ?? 0, 0),
      }),
    ]);
    return { stats, jobs };
  }

  async listNotifications(query: {
    recipient_id?: string;
    unread?: string;
    limit?: number;
  }): Promise<NotificationsListResponse> {
    await this.ensurePg();
    const recipientId = (query.recipient_id ?? 'ops').trim() || 'ops';
    const { rows, unread } = await this.repo.listNotifications({
      recipientId,
      unreadOnly: query.unread === '1',
      limit: Math.min(Math.max(query.limit ?? 50, 1), 200),
    });
    return { notifications: rows, unread };
  }

  async hubCampaignMaps(
    clientId: string,
    query: { channel?: string; include_inactive?: string; limit?: number },
  ): Promise<HubCampaignMapsResponse> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const activeOnly = query.include_inactive?.trim() !== '1';
    const maps = await this.repo.listHubCampaignMaps(clientId, {
      channel: query.channel?.trim() || undefined,
      activeOnly,
      limit: Math.min(Math.max(query.limit ?? 100, 1), 200),
    });
    return { ok: true, client_id: clientId, maps, count: maps.length };
  }

  async hubCampaignMapsGlobal(query: {
    client_id?: string;
    campaign_id?: string;
    limit?: number;
  }): Promise<{ ok: boolean; maps: HubCampaignGlobalRow[]; count: number }> {
    await this.ensurePg();
    const campaignId =
      query.campaign_id?.trim() ? Math.trunc(Number(query.campaign_id)) : undefined;
    const maps = await this.repo.listHubCampaignMapsGlobal({
      clientId: query.client_id?.trim() || undefined,
      campaignId: Number.isFinite(campaignId) ? campaignId : undefined,
      limit: Math.min(Math.max(query.limit ?? 200, 1), 500),
    });
    return { ok: true, maps, count: maps.length };
  }

  async facebookHub(query: {
    days?: string;
    to?: string;
    date_to?: string;
    from?: string;
    date_from?: string;
    status?: string;
    client_id?: string;
    q?: string;
  }): Promise<FacebookHubResponse> {
    await this.ensurePg();
    const windowDays = Math.min(Math.max(Number(query.days ?? 7) || 7, 1), 90);
    const dateTo = (query.to ?? query.date_to ?? '').trim() || undefined;
    const dateFrom = (query.from ?? query.date_from ?? '').trim() || undefined;
    const clientId = normalizeHubClientUuid(query.client_id);
    const q = query.q?.trim() || undefined;
    const status = query.status?.trim() || undefined;

    const { clients, summary, dateFrom: df, dateTo: dt, windowDays: wd } =
      await this.repo.facebookHubSummary({
        windowDays,
        dateTo,
        dateFrom,
        status,
        clientId: clientId ?? undefined,
        q,
      });

    const alerts = this.buildFacebookHubAlerts(summary);

    return {
      ok: true,
      pg_ready: true,
      date_from: df,
      date_to: dt,
      window_days: wd,
      summary,
      clients,
      alerts,
      filters: {
        client_id: clientId,
        status: status ?? null,
        q: q ?? null,
      },
    };
  }

  async facebookHubExportCsv(query: {
    days?: string;
    to?: string;
    date_to?: string;
    from?: string;
    date_from?: string;
    status?: string;
    client_id?: string;
    q?: string;
    scope?: string;
  }): Promise<{ csv: string; filename: string }> {
    await this.ensurePg();
    const hub = await this.facebookHub(query);
    const scope = (query.scope ?? 'clients').trim().toLowerCase();
    const meta = { dateFrom: hub.date_from, dateTo: hub.date_to };

    if (scope === 'campaigns') {
      const rows = await this.repo.facebookHubCampaignExport({
        dateFrom: hub.date_from,
        dateTo: hub.date_to,
        clientId: hub.filters?.client_id ?? undefined,
        status: hub.filters?.status ?? undefined,
        q: hub.filters?.q ?? undefined,
      });
      return {
        csv: buildFacebookHubCampaignsCsv(rows, meta),
        filename: facebookHubExportFilename('campaigns', meta.dateFrom, meta.dateTo),
      };
    }

    return {
      csv: buildFacebookHubClientsCsv(hub.clients, meta),
      filename: facebookHubExportFilename('clients', meta.dateFrom, meta.dateTo),
    };
  }

  facebookAdsMigrationStatus(): Record<string, unknown> {
    const retired = this.isEnvTruthy('PTT_FLASK_META_ADS_ADMIN_RETIRED');
    const opsWeb = (process.env.PTT_OPS_WEB_URL ?? 'https://ops.pttads.vn').replace(/\/$/, '');
    const nginx = this.metaNginxRedirectStatus(opsWeb);
    const dryRun = this.metaRetirementDryRunStatus();
    const applied = this.metaRetirementApplyStatus();
    const autosync = checkAutosyncStandalone();
    const soak = evaluateSoakGate();
    const signoff = readMigrationSignoff();
    const gateM1G06 = Boolean(nginx.gate_m1_g06);
    return {
      ok: true,
      flask_meta_ads_admin_retired: retired,
      ops_web_hub_url: `${opsWeb}/meta/facebook-ads`,
      ops_web_migration_url: `${opsWeb}/meta/migration`,
      ops_web_hub_path: '/meta/facebook-ads',
      legacy_rs_path: '/crm/facebook-ads',
      canonical_upstream: retired ? 'ops-web' : 'flask',
      webhooks_nest_meta: this.isEnvTruthy('PTT_WEBHOOKS_NEST_META'),
      webhooks_flask_fallback: this.isEnvTruthy('PTT_WEBHOOKS_FLASK_FALLBACK'),
      gate_m1_g09: retired,
      gate_m1_g06: gateM1G06,
      gate_m1_g06_config: nginx.gate_m1_g06_config,
      gate_m1_g06_live: nginx.gate_m1_g06_live,
      nginx_redirect_live_skipped: nginx.live_verify_skipped,
      nginx_deploy_config_ok: nginx.deploy_config_ok,
      gate_m1_g11: dryRun.gate_m1_g11,
      retirement_dry_run_ok: dryRun.dry_run_artifact_ok,
      retirement_dry_run_artifact_present: dryRun.artifact_present,
      retirement_env_pending_changes: dryRun.env_pending_changes,
      retirement_env_already_applied: dryRun.env_already_applied,
      retirement_next_apply_command: dryRun.next_apply_command,
      gate_m1_g12: applied.gate_m1_g12,
      retirement_applied_ok: applied.retirement_applied_ok,
      retirement_env_applied_ok: applied.retirement_env_applied_ok,
      retirement_apply_artifact_present: applied.artifact_present,
      gate_m1_g07: autosync.gate_m1_g07,
      autosync_standalone_ok: autosync.autosync_standalone_ok,
      autosync_unit_present: autosync.autosync_unit_present,
      autosync_daemon_present: autosync.autosync_daemon_present,
      autosync_gunicorn_background_off: autosync.autosync_gunicorn_background_off,
      autosync_unit_no_ptt_dependency: autosync.autosync_unit_no_ptt_dependency,
      gate_m1_g08: soak.gate_m1_g08,
      soak_7d_ok: soak.soak_7d_ok,
      soak_span_days: soak.soak_span_days,
      soak_sample_count: soak.soak_sample_count,
      soak_required_days: soak.soak_required_days,
      soak_min_samples: soak.soak_min_samples,
      soak_failure_count: soak.soak_failure_count,
      soak_latest_recorded_at: soak.soak_latest_recorded_at,
      soak_error: soak.soak_error,
      manual_uat: signoff.manual_uat,
      manual_uat_updated_at: signoff.updated_at,
      signoff_path: signoff.path,
      horizon1_expect_meta_hub_retired: this.isEnvTruthy('HORIZON1_EXPECT_META_HUB_RETIRED'),
    };
  }

  facebookAdsMigrationSignoff(): Record<string, unknown> {
    return readMigrationSignoff();
  }

  patchFacebookAdsMigrationManualUat(updates: Partial<ManualUatState>): Record<string, unknown> {
    try {
      return writeManualUat(updates);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message === 'signoff_template_missing') {
        throw new ServiceUnavailableException({ error: 'signoff_template_missing' });
      }
      throw err;
    }
  }

  private metaRetirementApplyStatus(): {
    gate_m1_g12: boolean;
    retirement_applied_ok: boolean | null;
    retirement_env_applied_ok: boolean | null;
    artifact_present: boolean;
  } {
    const root = path.resolve(process.cwd(), '../..');
    const artifactPath = path.join(root, '.local-dev/horizon1-meta-ads-retirement-applied.json');
    const envApplied = this.isEnvTruthy('HORIZON1_META_RETIREMENT_APPLIED', '0');
    try {
      const raw = fs.readFileSync(artifactPath, 'utf8');
      const data = JSON.parse(raw) as { ok?: boolean; applied?: boolean };
      const ok = Boolean(data.ok) && data.applied !== false;
      return {
        gate_m1_g12: ok,
        retirement_applied_ok: ok,
        retirement_env_applied_ok: ok,
        artifact_present: true,
      };
    } catch {
      return {
        gate_m1_g12: envApplied,
        retirement_applied_ok: envApplied ? true : null,
        retirement_env_applied_ok: envApplied ? true : null,
        artifact_present: false,
      };
    }
  }

  private metaRetirementDryRunStatus(): {
    gate_m1_g11: boolean;
    dry_run_artifact_ok: boolean | null;
    artifact_present: boolean;
    env_pending_changes: number | null;
    env_already_applied: boolean | null;
    next_apply_command: string;
  } {
    const root = path.resolve(process.cwd(), '../..');
    const artifactPath = path.join(root, '.local-dev/horizon1-meta-ads-retirement-dry-run.json');
    const nextApply = 'sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh';
    try {
      const raw = fs.readFileSync(artifactPath, 'utf8');
      const data = JSON.parse(raw) as {
        ok?: boolean;
        dry_run?: boolean;
        steps?: { env_diff?: { pending_changes?: number; already_applied?: boolean } };
      };
      if (data.dry_run !== true) {
        return {
          gate_m1_g11: false,
          dry_run_artifact_ok: false,
          artifact_present: true,
          env_pending_changes: null,
          env_already_applied: null,
          next_apply_command: nextApply,
        };
      }
      const envDiff = data.steps?.env_diff;
      return {
        gate_m1_g11: Boolean(data.ok),
        dry_run_artifact_ok: Boolean(data.ok),
        artifact_present: true,
        env_pending_changes:
          typeof envDiff?.pending_changes === 'number' ? envDiff.pending_changes : null,
        env_already_applied:
          typeof envDiff?.already_applied === 'boolean' ? envDiff.already_applied : null,
        next_apply_command: nextApply,
      };
    } catch {
      const verified = this.isEnvTruthy('HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED', '0');
      return {
        gate_m1_g11: verified,
        dry_run_artifact_ok: verified ? true : null,
        artifact_present: false,
        env_pending_changes: null,
        env_already_applied: null,
        next_apply_command: nextApply,
      };
    }
  }

  private metaNginxRedirectStatus(_opsWebBase: string): {
    gate_m1_g06: boolean;
    gate_m1_g06_config: boolean;
    gate_m1_g06_live: boolean | null;
    live_verify_skipped: boolean;
    deploy_config_ok: boolean;
  } {
    const hubPath = '/meta/facebook-ads';
    const deployOk = this.metaNginxDeployConfigOk(hubPath);
    const liveSkipped = this.isEnvTruthy('HORIZON1_SKIP_NGINX_REDIRECT_VERIFY', '1');
    const liveVerified = this.isEnvTruthy('HORIZON1_META_NGINX_REDIRECT_VERIFIED', '0');
    const configOk = deployOk;
    const liveOk = liveSkipped ? null : liveVerified;
    const gateOk = configOk && (liveOk !== false);
    return {
      gate_m1_g06: gateOk,
      gate_m1_g06_config: configOk,
      gate_m1_g06_live: liveOk,
      live_verify_skipped: liveSkipped,
      deploy_config_ok: deployOk,
    };
  }

  private metaNginxDeployConfigOk(hubPath: string): boolean {
    const root = path.resolve(process.cwd(), '../..');
    const candidates = [
      path.join(root, 'deploy/nginx-rs-delivery-admin-retired.conf'),
      path.join(root, 'deploy/nginx-meta-ads-retired-snippet.conf'),
    ];
    const needlePath = '/crm/facebook-ads';
    for (const file of candidates) {
      try {
        const text = fs.readFileSync(file, 'utf8');
        if (text.includes(needlePath) && text.includes(hubPath)) {
          return true;
        }
      } catch {
        // missing file — try next
      }
    }
    return false;
  }

  private isEnvTruthy(name: string, defaultValue = '0'): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env[name] ?? defaultValue).trim().toLowerCase(),
    );
  }

  private buildFacebookHubAlerts(summary: Record<string, unknown>): FacebookHubAlert[] {
    const alerts: FacebookHubAlert[] = [];
    const unmapped = Number(summary.unmapped_campaigns ?? 0);
    const overTarget = Number(summary.over_target_rows ?? 0);
    if (unmapped > 0) {
      alerts.push({
        severity: 'warn',
        message: `${unmapped} campaign Meta chưa map Hub`,
        link: '/crm/hub',
        link_label: 'Mở Hub map',
      });
    }
    if (overTarget > 0) {
      alerts.push({
        severity: 'warn',
        message: `${overTarget} dòng CPL vượt target trong kỳ đã chọn`,
        link: '/meta/facebook-ads',
        link_label: 'Xem bảng client',
      });
    }
    return alerts;
  }

  private onboardingProgressFromItems(
    items: Array<{ completed: boolean }>,
  ): { total: number; completed: number; percent: number } {
    const total = items.length;
    const completed = items.filter((i) => i.completed).length;
    const percent = total ? Math.round((completed / total) * 100) : 0;
    return { total, completed, percent };
  }

  async updateClient(clientId: string, body: UpdateClientBody): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const row = await this.repo.updateClient(clientId, body);
    if (!row) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return this.getClient(clientId);
  }

  async getOnboarding(clientId: string): Promise<OnboardingResponse> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const items = await this.repo.listOnboardingItems(clientId);
    return { items, progress: this.onboardingProgressFromItems(items) };
  }

  async patchOnboardingItem(
    clientId: string,
    itemKey: string,
    body: { completed: boolean; completed_by?: string; note?: string },
  ): Promise<OnboardingResponse> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const ok = await this.repo.setOnboardingItem(clientId, itemKey, body);
    if (!ok) {
      throw new NotFoundException({ error: 'item_not_found' });
    }
    const workflowSignal = await this.sideEffects.onOnboardingPatched(clientId);
    const response = await this.getOnboarding(clientId);
    return { ...response, side_effects: workflowSignal ? { workflow_signal: workflowSignal } : undefined };
  }

  async getOnboardingWorkflowStatus(clientId: string) {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return this.workflows.onboardingStatus(clientId);
  }

  private buildWorkflowSnapshot(raw: {
    workflow_id?: string;
    status?: string;
    run_id?: string | null;
    found?: boolean;
  }): OnboardingWorkflowSnapshot {
    const temporalEnabled = Boolean(process.env.TEMPORAL_ADDRESS?.trim());
    return {
      workflow_id: String(raw.workflow_id ?? ''),
      status: String(raw.status ?? 'UNKNOWN'),
      run_id: raw.run_id ?? null,
      found: Boolean(raw.found),
      temporal_enabled: temporalEnabled,
    };
  }

  async getOnboardingSummary(clientId: string): Promise<OnboardingSummaryResponse> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const [onboarding, wfRaw] = await Promise.all([
      this.getOnboarding(clientId),
      this.workflows.onboardingStatus(clientId),
    ]);
    const workflow = this.buildWorkflowSnapshot(wfRaw);
    const linked = this.contractSqlite.findLifecyclesByAgencyClientId(clientId).map((row) => ({
      lifecycle_id: row.lifecycle_id,
      stage: row.stage,
      status: row.status,
      service_slug: row.service_slug,
      contract_id: row.contract_id,
      contract_title: row.contract_title,
      service_delivery_url: `/crm/service-delivery/${row.lifecycle_id}`,
    }));
    const strict = strictOnboardingEnabled();
    const activationReady =
      client.status === 'active' || onboarding.progress.percent >= 100 || !strict;
    return {
      ...onboarding,
      client_id: clientId,
      client_status: client.status,
      client_code: client.code,
      client_name: client.name,
      workflow,
      strict_onboarding: strict,
      activation_ready: activationReady,
      linked_lifecycles: linked,
    };
  }

  async nudgeOnboardingWorkflow(clientId: string) {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const out = await this.workflows.nudgeOnboarding(clientId);
    return { client_id: clientId, ...out };
  }

  async startOnboardingWorkflow(clientId: string, startedBy?: string) {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return this.workflows.startOnboarding({
      client_id: clientId,
      started_by: startedBy?.trim() || 'am@pttads.vn',
    });
  }

  async activateClient(clientId: string, force = false): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const onboarding = await this.getOnboarding(clientId);
    if (strictOnboardingEnabled() && !force && onboarding.progress.percent < 100) {
      throw new BadRequestException({
        error: 'checklist_incomplete',
        progress: onboarding.progress,
      });
    }
    const row = await this.repo.updateClient(clientId, { status: 'active' });
    if (!row) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const effects = await this.sideEffects.onClientActivated(clientId, client.code);
    const detail = await this.getClient(clientId);
    return {
      ...detail,
      side_effects: this.mapSideEffects(effects),
    };
  }

  private mapSideEffects(effects: {
    domain_event_id: string | null;
    jobs_enqueued: Array<{ id: string; job_type: string; status: string; created: boolean }>;
    workflow_signal?: string;
  }): AgencySideEffectsSummary {
    return {
      domain_event_id: effects.domain_event_id,
      jobs_enqueued: effects.jobs_enqueued.map((j) => ({
        id: j.id,
        job_type: j.job_type,
        status: j.status,
        created: j.created,
      })),
      workflow_signal: effects.workflow_signal,
    };
  }

  async addChannelAccount(clientId: string, body: AddChannelAccountBody): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const channel = body.channel?.trim().toLowerCase() ?? '';
    if (!VALID_CHANNELS.has(channel)) {
      throw new BadRequestException({ error: 'invalid_channel' });
    }
    const ext = body.external_account_id?.trim() ?? '';
    if (!ext) {
      throw new BadRequestException({ error: 'external_account_id_required' });
    }
    await this.repo.addChannelAccount(clientId, {
      channel,
      external_account_id: ext,
      display_name: body.display_name,
      facebook_page_id: body.facebook_page_id,
    });
    return this.getClient(clientId);
  }

  async updateChannelAccount(
    clientId: string,
    accountId: string,
    body: UpdateChannelAccountBody,
  ): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    if (body.status !== undefined && !VALID_CHANNEL_STATUSES.has(body.status.trim())) {
      throw new BadRequestException({ error: 'invalid_status' });
    }
    try {
      const updated = await this.repo.updateChannelAccount(clientId, accountId, {
        display_name: body.display_name,
        external_account_id: body.external_account_id,
        status: body.status?.trim(),
        facebook_page_id: body.facebook_page_id,
      });
      if (!updated) {
        throw new NotFoundException({ error: 'account_not_found' });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const pgCode = err && typeof err === 'object' && 'code' in err ? String((err as { code?: string }).code) : '';
      if (msg === 'external_account_id_required') {
        throw new BadRequestException({ error: msg });
      }
      if (pgCode === '23505' || msg.includes('unique') || msg.includes('duplicate')) {
        throw new BadRequestException({ error: 'channel_account_conflict' });
      }
      throw err;
    }
    return this.getClient(clientId);
  }

  async deleteChannelAccount(clientId: string, accountId: string): Promise<{ ok: boolean }> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const deleted = await this.repo.deleteChannelAccount(clientId, accountId);
    if (!deleted) {
      throw new NotFoundException({ error: 'account_not_found' });
    }
    return { ok: true };
  }

  async setChannelAccountToken(
    clientId: string,
    accountId: string,
    body: SetChannelTokenBody,
  ): Promise<AgencyClientDetail & { side_effects?: AgencySideEffectsSummary }> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    try {
      await this.repo.setChannelAccountToken(clientId, accountId, body);
    } catch (err) {
      if (err instanceof TokenVaultError) {
        throw new BadRequestException({ error: 'vault_not_configured', message: err.message });
      }
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('DDL v3')) {
        throw new ServiceUnavailableException({ error: 'vault_ddl_missing', message: msg });
      }
      if (msg === 'account_not_found') {
        throw new NotFoundException({ error: 'account_not_found' });
      }
      throw new BadRequestException({ error: msg });
    }
    const account = await this.repo.fetchChannelAccount(clientId, accountId);
    let jobs: AgencySideEffectsSummary['jobs_enqueued'];
    if (account?.channel === 'meta' && account.has_token && !body.revoke) {
      const enqueued = await this.sideEffects.enqueueMetaInsightsSync(clientId);
      jobs = enqueued.map((j) => ({
        id: j.id,
        job_type: j.job_type,
        status: j.status,
        created: j.created,
      }));
    }
    const detail = await this.getClient(clientId);
    return jobs?.length ? { ...detail, side_effects: { jobs_enqueued: jobs } } : detail;
  }

  async syncClientInsights(clientId: string): Promise<{ ok: boolean; jobs_enqueued: AgencySideEffectsSummary['jobs_enqueued'] }> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const jobs = await this.sideEffects.enqueueMetaInsightsSync(clientId);
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

  async listClientLeads(clientId: string): Promise<{ leads: ClientLeadRow[] }> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const leads = await this.repo.listClientLeads(clientId);
    return { leads };
  }

  async replayJob(jobId: string): Promise<{ id: string; status: string; replayed: boolean }> {
    await this.ensurePg();
    const out = await this.repo.replayJob(jobId);
    if (!out) {
      throw new BadRequestException({ error: 'job_not_replayable', hint: 'Chỉ replay job status=dead' });
    }
    return out;
  }

  async markNotificationRead(notificationId: string, recipientId: string): Promise<{ ok: boolean }> {
    await this.ensurePg();
    const ok = await this.repo.markNotificationRead(notificationId, recipientId);
    if (!ok) {
      throw new NotFoundException({ error: 'not_found' });
    }
    return { ok: true };
  }

  async markAllNotificationsRead(recipientId: string): Promise<{ marked: number }> {
    await this.ensurePg();
    const marked = await this.repo.markAllNotificationsRead(recipientId);
    return { marked };
  }

  async listKpiDefinitions(): Promise<{ definitions: KpiDefinitionRow[] }> {
    await this.ensurePg();
    const definitions = await this.repo.listKpiDefinitions();
    return { definitions };
  }

  async createKpiDefinition(body: CreateKpiDefinitionBody): Promise<{ definition: KpiDefinitionRow }> {
    await this.ensurePg();
    const code = body.code?.trim() ?? '';
    if (!/^[A-Z0-9_]{2,40}$/.test(code.toUpperCase())) {
      throw new BadRequestException({ error: 'invalid_code' });
    }
    if (!body.name?.trim() || !body.formula?.trim()) {
      throw new BadRequestException({ error: 'name_and_formula_required' });
    }
    try {
      const row = await this.repo.createKpiDefinition(body);
      return { definition: row };
    } catch (err) {
      this.logger.warn(`createKpiDefinition failed: ${String(err)}`);
      throw new BadRequestException({ error: 'create_failed', hint: 'code trùng?' });
    }
  }

  async updateKpiDefinition(code: string, body: UpdateKpiDefinitionBody): Promise<{ ok: boolean }> {
    await this.ensurePg();
    const ok = await this.repo.updateKpiDefinition(code, body);
    if (!ok) {
      throw new NotFoundException({ error: 'not_found' });
    }
    return { ok: true };
  }

  async deleteKpiDefinition(code: string): Promise<{ ok: boolean }> {
    await this.ensurePg();
    const ok = await this.repo.deleteKpiDefinition(code);
    if (!ok) {
      throw new NotFoundException({ error: 'not_found' });
    }
    return { ok: true };
  }

  async patchHubCampaignMap(body: PatchHubCampaignMapBody): Promise<{ ok: boolean; map_id: string; external_campaign_id: string }> {
    await this.ensurePg();
    const clientId = body.client_id?.trim() ?? '';
    const hubCampaignId = Math.trunc(Number(body.hub_campaign_id));
    const externalId = normalizeMetaCampaignId(body.external_campaign_id ?? '');
    if (!clientId || !Number.isFinite(hubCampaignId) || hubCampaignId <= 0) {
      throw new BadRequestException({ error: 'invalid_payload' });
    }
    validateExternalCampaignId('meta', externalId);
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'client_not_found' });
    }
    const out = await this.repo.updateHubCampaignMap({
      clientId,
      hubCampaignId,
      externalCampaignId: externalId,
    });
    if (!out) {
      throw new NotFoundException({ error: 'map_not_found' });
    }
    await this.maybeEnqueueInsightsAfterMapChange(clientId, 'meta');
    return { ok: true, ...out };
  }

  async createHubCampaignMap(
    body: CreateHubCampaignMapBody,
  ): Promise<{ ok: boolean; map: HubCampaignMapRow; jobs_enqueued?: AgencySideEffectsSummary['jobs_enqueued'] }> {
    await this.ensurePg();
    const clientId = body.client_id?.trim() ?? '';
    const channel = (body.channel?.trim() || 'meta').toLowerCase();
    const externalId = normalizeExternalCampaignId(channel, body.external_campaign_id ?? '');
    if (!clientId) {
      throw new BadRequestException({ error: 'client_id_required' });
    }
    if (!VALID_HUB_CHANNELS.has(channel)) {
      throw new BadRequestException({ error: 'invalid_channel' });
    }
    validateExternalCampaignId(channel, externalId);
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'client_not_found' });
    }

    let hubCampaignId = body.hub_campaign_id != null ? Math.trunc(Number(body.hub_campaign_id)) : 0;
    if (!Number.isFinite(hubCampaignId) || hubCampaignId <= 0) {
      hubCampaignId = await this.repo.allocateAgencyHubCampaignId();
    }

    let externalAccountId = body.external_account_id?.trim() || null;
    if (!externalAccountId && channel === 'meta') {
      externalAccountId = await this.repo.resolveMetaAccountId(clientId);
    }

    let targetCpl: number | null = null;
    if (body.target_cpl_vnd != null && Number.isFinite(Number(body.target_cpl_vnd))) {
      const n = Number(body.target_cpl_vnd);
      targetCpl = n > 0 ? Math.round(n * 100) / 100 : null;
    }

    try {
      const map = await this.repo.createHubCampaignMap({
        clientId,
        hubCampaignId,
        channel,
        externalCampaignId: externalId,
        externalCampaignName: body.external_campaign_name?.trim() || null,
        externalAccountId,
        targetCplVnd: targetCpl,
      });
      const jobs = await this.maybeEnqueueInsightsAfterMapChange(clientId, channel);
      return {
        ok: true,
        map,
        ...(jobs?.length ? { jobs_enqueued: jobs } : {}),
      };
    } catch (err) {
      const msg = String(err);
      if (msg.includes('unique') || msg.includes('duplicate')) {
        throw new BadRequestException({ error: 'duplicate_map', hint: 'Campaign ID đã map cho client này' });
      }
      this.logger.warn(`createHubCampaignMap failed: ${msg}`);
      throw new BadRequestException({ error: 'create_failed' });
    }
  }

  async updateHubCampaignMapById(
    mapId: string,
    body: UpdateHubCampaignMapBody,
    clientId?: string,
  ): Promise<{ ok: boolean; map: HubCampaignMapRow; jobs_enqueued?: AgencySideEffectsSummary['jobs_enqueued'] }> {
    await this.ensurePg();
    const existing = await this.repo.fetchHubCampaignMapById(mapId, clientId);
    if (!existing) {
      throw new NotFoundException({ error: 'map_not_found' });
    }

    const channel = existing.channel;
    let externalId: string | undefined;
    if (body.external_campaign_id !== undefined) {
      externalId = normalizeExternalCampaignId(channel, body.external_campaign_id);
      validateExternalCampaignId(channel, externalId);
    }

    let targetCpl: number | null | undefined;
    if (body.target_cpl_vnd !== undefined) {
      if (body.target_cpl_vnd == null) {
        targetCpl = null;
      } else {
        const n = Number(body.target_cpl_vnd);
        targetCpl = Number.isFinite(n) && n > 0 ? Math.round(n * 100) / 100 : null;
      }
    }

    try {
      const map = await this.repo.updateHubCampaignMapById(mapId, {
        clientId,
        externalCampaignId: externalId,
        externalCampaignName:
          body.external_campaign_name !== undefined
            ? body.external_campaign_name?.trim() || null
            : undefined,
        externalAccountId:
          body.external_account_id !== undefined
            ? body.external_account_id?.trim() || null
            : undefined,
        targetCplVnd: targetCpl,
        active: body.active,
      });
      if (!map) {
        throw new NotFoundException({ error: 'map_not_found' });
      }
      const jobs = await this.maybeEnqueueInsightsAfterMapChange(existing.client_id, channel);
      return {
        ok: true,
        map,
        ...(jobs?.length ? { jobs_enqueued: jobs } : {}),
      };
    } catch (err) {
      if (err instanceof NotFoundException || err instanceof BadRequestException) throw err;
      const msg = String(err);
      if (msg.includes('unique') || msg.includes('duplicate')) {
        throw new BadRequestException({ error: 'duplicate_map' });
      }
      throw err;
    }
  }

  async deleteHubCampaignMapById(
    mapId: string,
    clientId?: string,
  ): Promise<{ ok: boolean }> {
    await this.ensurePg();
    const existing = await this.repo.fetchHubCampaignMapById(mapId, clientId);
    if (!existing) {
      throw new NotFoundException({ error: 'map_not_found' });
    }
    const ok = await this.repo.deleteHubCampaignMapById(mapId, clientId);
    if (!ok) {
      throw new NotFoundException({ error: 'map_not_found' });
    }
    return { ok: true };
  }

  private async maybeEnqueueInsightsAfterMapChange(
    clientId: string,
    channel: string,
  ): Promise<AgencySideEffectsSummary['jobs_enqueued'] | undefined> {
    if (channel !== 'meta') return undefined;
    const jobsEnabled = (process.env.PTT_JOBS_ENABLED ?? '').trim();
    if (jobsEnabled !== '1' && jobsEnabled.toLowerCase() !== 'true') return undefined;
    try {
      const jobs = await this.sideEffects.enqueueMetaInsightsSync(clientId);
      return jobs.map((j) => ({
        id: j.id,
        job_type: j.job_type,
        status: j.status,
        created: j.created,
      }));
    } catch (err) {
      this.logger.warn(`enqueue insights after hub map: ${String(err)}`);
      return undefined;
    }
  }
}
