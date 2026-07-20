import {
  ForbiddenException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import { EmailSendOrchestratorService } from '../email-marketing/email-send-orchestrator.service';
import { PortalEmailRepository } from './portal-email.repository';
import {
  PortalEmailApprovalDecision,
  PortalEmailApprovalPreview,
  PortalEmailApprovalRow,
  PortalEmailCampaignRow,
  PortalEmailCampaignStats,
  PortalEmailDashboard,
  PortalEmailReportsSummary,
} from './portal-email.types';

@Injectable()
export class PortalEmailService {
  constructor(
    private readonly repo: PortalEmailRepository,
    private readonly sendOrchestrator: EmailSendOrchestratorService,
  ) {}

  private portalEmailEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_EMAIL_PORTAL_ENABLED ?? '1').trim().toLowerCase(),
    );
  }

  assertEnabled(): void {
    if (!this.portalEmailEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'portal_email_disabled' });
    }
  }

  private assertClient(user: PortalJwtPayload): string {
    if (!user.client_id) {
      throw new ForbiddenException({ error: 'missing_client_id' });
    }
    return user.client_id;
  }

  private assertApprover(user: PortalJwtPayload): void {
    if (user.role !== 'approver') {
      throw new ForbiddenException({ error: 'approver_role_required' });
    }
  }

  async dashboard(user: PortalJwtPayload): Promise<PortalEmailDashboard> {
    this.assertEnabled();
    const clientId = this.assertClient(user);
    const ready = await this.repo.schemaReady();
    if (!ready) {
      return {
        ok: true,
        email_enabled: false,
        client_id: clientId,
        pending_approvals: 0,
        campaigns_sent_28d: 0,
        open_rate_pct: 0,
        revenue_attrib: 0,
        recent_campaigns: [],
      };
    }
    const hasWs = await this.repo.hasWorkspace(clientId);
    if (!hasWs) {
      return {
        ok: true,
        email_enabled: false,
        client_id: clientId,
        pending_approvals: 0,
        campaigns_sent_28d: 0,
        open_rate_pct: 0,
        revenue_attrib: 0,
        recent_campaigns: [],
      };
    }
    return this.repo.dashboard(clientId);
  }

  async listCampaigns(user: PortalJwtPayload): Promise<{ ok: boolean; items: PortalEmailCampaignRow[] }> {
    this.assertEnabled();
    const clientId = this.assertClient(user);
    if (!(await this.repo.schemaReady())) {
      return { ok: true, items: [] };
    }
    const items = await this.repo.listCampaigns(clientId);
    return { ok: true, items };
  }

  async campaignStats(user: PortalJwtPayload, campaignId: string): Promise<PortalEmailCampaignStats> {
    this.assertEnabled();
    const clientId = this.assertClient(user);
    if (!(await this.repo.schemaReady())) {
      throw new NotFoundException({ error: 'email_schema_not_ready' });
    }
    return this.repo.campaignStats(clientId, campaignId);
  }

  async pendingApprovals(
    user: PortalJwtPayload,
  ): Promise<{ ok: boolean; items: PortalEmailApprovalRow[] }> {
    this.assertEnabled();
    const clientId = this.assertClient(user);
    if (!(await this.repo.schemaReady())) {
      return { ok: true, items: [] };
    }
    const items = await this.repo.pendingApprovals(clientId);
    return { ok: true, items };
  }

  async approvalPreview(user: PortalJwtPayload, campaignId: string): Promise<PortalEmailApprovalPreview> {
    this.assertEnabled();
    const clientId = this.assertClient(user);
    if (!(await this.repo.schemaReady())) {
      throw new NotFoundException({ error: 'email_schema_not_ready' });
    }
    const row = await this.repo.approvalPreview(clientId, campaignId);
    if (!row) throw new NotFoundException({ error: 'campaign_not_found' });
    return { ok: true, ...row };
  }

  async approveCampaign(
    user: PortalJwtPayload,
    campaignId: string,
  ): Promise<{ ok: boolean; campaign: PortalEmailCampaignRow }> {
    this.assertEnabled();
    this.assertApprover(user);
    const clientId = this.assertClient(user);
    const campaign = await this.repo.approveCampaign({
      clientId,
      campaignId,
      actor: user.email,
    });
    await this.sendOrchestrator.onCampaignApproved({
      campaignId,
      clientId,
      reviewedBy: user.email,
    });
    return { ok: true, campaign };
  }

  async rejectCampaign(
    user: PortalJwtPayload,
    campaignId: string,
    body: PortalEmailApprovalDecision,
  ): Promise<{ ok: boolean; campaign: PortalEmailCampaignRow }> {
    this.assertEnabled();
    this.assertApprover(user);
    const clientId = this.assertClient(user);
    const campaign = await this.repo.rejectCampaign({
      clientId,
      campaignId,
      actor: user.email,
      note: body.note,
    });
    await this.sendOrchestrator.signalRejectOnly(campaignId, user.email, body.note);
    return { ok: true, campaign };
  }

  async reportsSummary(user: PortalJwtPayload, days?: number): Promise<PortalEmailReportsSummary> {
    this.assertEnabled();
    const clientId = this.assertClient(user);
    const safeDays = Number.isFinite(days) && (days ?? 0) > 0 ? Math.min(days ?? 28, 365) : 28;
    if (!(await this.repo.schemaReady())) {
      return {
        ok: true,
        client_id: clientId,
        days: safeDays,
        sent: 0,
        opens: 0,
        clicks: 0,
        open_rate_pct: 0,
        revenue_attrib: 0,
      };
    }
    return this.repo.reportsSummary(clientId, safeDays);
  }
}
