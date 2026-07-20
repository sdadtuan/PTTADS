import {
  ForbiddenException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import { PortalSeoRepository } from './portal-seo.repository';
import {
  PortalSeoContentDetail,
  PortalSeoContentRow,
  PortalSeoExecutiveReport,
  PortalSeoReportType,
  PortalSeoReviewBody,
  PortalSeoSummary,
  PortalSeoWidgets,
} from './portal-seo.types';

function sanitizePortalDashboard(data: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...data };
  const issues = out.issues;
  if (Array.isArray(issues)) {
    out.issues = issues
      .filter((item): item is Record<string, unknown> => typeof item === 'object' && item != null)
      .map((item) => ({
        url: item.url ?? '',
        issue_type: item.issue_type ?? '',
        severity: item.severity ?? '',
        status: item.status ?? '',
      }));
  }
  const mentions = out.mentions_recent;
  if (Array.isArray(mentions)) {
    out.mentions_recent = mentions
      .filter((item): item is Record<string, unknown> => typeof item === 'object' && item != null)
      .map((item) => ({
        stat_date: item.stat_date,
        mention_count: item.mention_count,
        citation_status: item.citation_status,
      }));
  }
  const syncKey = out.sync_runs_recent != null ? 'sync_runs_recent' : out.sync_runs != null ? 'sync_runs' : null;
  if (syncKey) {
    const syncRuns = out[syncKey];
    if (Array.isArray(syncRuns)) {
      out[syncKey] = syncRuns
        .filter((item): item is Record<string, unknown> => typeof item === 'object' && item != null)
        .map((item) => ({
          source: item.source ?? item.connector ?? '',
          status: item.status ?? '',
          finished_at: item.finished_at ?? item.created_at,
        }));
    }
  }
  return out;
}

@Injectable()
export class PortalSeoService {
  constructor(private readonly repo: PortalSeoRepository) {}

  private portalSeoEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_PORTAL_SEO_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  assertEnabled(): void {
    if (!this.portalSeoEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'portal_seo_disabled' });
    }
  }

  private async resolveCustomerId(clientId: string): Promise<number | null> {
    try {
      return await this.repo.customerIdForPortalClient(clientId);
    } catch {
      throw new ServiceUnavailableException({ ok: false, error: 'seo_pg_unavailable' });
    }
  }

  async executiveReport(
    user: PortalJwtPayload,
    dashboardType: PortalSeoReportType = 'executive',
  ): Promise<PortalSeoExecutiveReport> {
    this.assertEnabled();
    const customerId = await this.resolveCustomerId(user.client_id);
    if (customerId == null) {
      throw new NotFoundException({ ok: false, error: 'seo_not_mapped' });
    }
    const report = sanitizePortalDashboard(await this.repo.buildDashboard(customerId, dashboardType));
    return {
      ok: true,
      customer_id: customerId,
      dashboard_type: dashboardType,
      report,
      generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    };
  }

  async summary(user: PortalJwtPayload): Promise<PortalSeoSummary> {
    this.assertEnabled();
    const customerId = await this.resolveCustomerId(user.client_id);
    if (customerId == null) {
      return { seo_enabled: false, error: 'not_mapped' };
    }
    const execReport = await this.executiveReport(user, 'executive');
    const pending = await this.repo.listPendingContent(customerId);
    return {
      seo_enabled: true,
      customer_id: customerId,
      executive: execReport.report,
      pending_client_review: pending.length,
    };
  }

  async widgets(user: PortalJwtPayload): Promise<PortalSeoWidgets> {
    this.assertEnabled();
    const customerId = await this.resolveCustomerId(user.client_id);
    if (customerId == null) {
      throw new NotFoundException({ ok: false, error: 'seo_not_mapped' });
    }
    const execDash = sanitizePortalDashboard(await this.repo.buildDashboard(customerId, 'executive'));
    const pendingReview = (await this.repo.listPendingContent(customerId)).length;
    const gsc = (execDash.gsc as Record<string, unknown> | undefined) ?? {};
    const aeo = (execDash.aeo as Record<string, unknown> | undefined) ?? {};
    const trend = (execDash.gsc_trend as Array<Record<string, unknown>> | undefined) ?? [];
    const sparkline = trend.slice(-7).map((point) => Number(point.clicks ?? 0));
    return {
      ok: true,
      customer_id: customerId,
      widgets: {
        gsc_clicks: {
          label: 'GSC Clicks (T-7)',
          value: gsc.clicks,
          sparkline,
        },
        gsc_impressions: {
          label: 'Impressions',
          value: gsc.impressions,
        },
        critical_issues: {
          label: 'Critical issues',
          value: execDash.critical_issues ?? 0,
        },
        aeo_coverage: {
          label: 'AEO coverage',
          value: aeo.coverage_pct,
          unit: '%',
        },
        open_alerts: {
          label: 'Open alerts',
          value: execDash.open_alerts ?? 0,
        },
        content_in_review: {
          label: 'Pending review',
          value: pendingReview,
        },
      },
    };
  }

  async pendingContent(user: PortalJwtPayload): Promise<{ ok: boolean; items: PortalSeoContentRow[] }> {
    this.assertEnabled();
    const customerId = await this.resolveCustomerId(user.client_id);
    if (customerId == null) {
      throw new NotFoundException({ ok: false, error: 'seo_not_mapped' });
    }
    const items = await this.repo.listPendingContent(customerId);
    return { ok: true, items };
  }

  async contentDetail(user: PortalJwtPayload, contentId: string): Promise<PortalSeoContentDetail> {
    this.assertEnabled();
    const customerId = await this.resolveCustomerId(user.client_id);
    if (customerId == null) {
      throw new NotFoundException({ ok: false, error: 'seo_not_mapped' });
    }
    const parsedId = Number.parseInt(contentId, 10);
    if (!Number.isFinite(parsedId)) {
      throw new NotFoundException({ ok: false, error: 'content_not_found' });
    }
    const content = await this.repo.getContentDetail(customerId, parsedId);
    if (!content) {
      throw new NotFoundException({ ok: false, error: 'content_not_found' });
    }
    return content;
  }

  async reviewContent(
    user: PortalJwtPayload,
    contentId: string,
    body: PortalSeoReviewBody,
  ): Promise<{ ok: boolean; content: PortalSeoContentDetail }> {
    this.assertEnabled();
    if (user.role !== 'approver') {
      throw new ForbiddenException({ ok: false, error: 'approver_required' });
    }
    const customerId = await this.resolveCustomerId(user.client_id);
    if (customerId == null) {
      throw new NotFoundException({ ok: false, error: 'seo_not_mapped' });
    }
    const parsedId = Number.parseInt(contentId, 10);
    if (!Number.isFinite(parsedId)) {
      throw new NotFoundException({ ok: false, error: 'content_not_found' });
    }
    const content = await this.repo.reviewContent({
      customerId,
      contentId: parsedId,
      approved: body.approved,
      actorId: user.email,
      notes: body.notes ?? '',
    });
    return { ok: true, content };
  }
}
