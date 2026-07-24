import { Injectable, NotFoundException } from '@nestjs/common';
import { MetaComplianceRepository } from './meta-compliance.repository';
import { COMPLIANCE_EXPORT_VERSION, MetaComplianceExportResponse } from './meta-compliance.types';

@Injectable()
export class MetaComplianceService {
  constructor(private readonly repo: MetaComplianceRepository) {}

  isEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_COMPLIANCE_EXPORT_ENABLED ?? '1').trim().toLowerCase(),
    );
  }

  async exportBundle(clientId: string, daysRaw?: string): Promise<MetaComplianceExportResponse> {
    if (!this.isEnabled()) {
      return {
        ok: false,
        export_version: COMPLIANCE_EXPORT_VERSION,
        generated_at: new Date().toISOString(),
        client_id: clientId,
        client: null,
        channel_accounts: [],
        performance_summary: {},
        open_alerts: [],
        recent_campaign_writes: [],
        tracking_summary: {},
        redaction: {
          tokens_redacted: true,
          pii_redacted: true,
          note: 'PTT_META_COMPLIANCE_EXPORT_ENABLED=0',
        },
      };
    }

    const days = Math.min(Math.max(Number(daysRaw ?? 30) || 30, 1), 90);
    const exists = await this.repo.clientExists(clientId);
    if (!exists) {
      throw new NotFoundException({ error: 'client_not_found' });
    }

    const [client, channelAccounts, performanceSummary, openAlerts, recentWrites, trackingSummary] =
      await Promise.all([
        this.repo.fetchClient(clientId),
        this.repo.fetchChannelAccounts(clientId),
        this.repo.fetchPerformanceSummary(clientId, days),
        this.repo.fetchOpenAlerts(clientId),
        this.repo.fetchRecentCampaignWrites(clientId),
        this.repo.fetchTrackingSummary(clientId, days),
      ]);

    return {
      ok: true,
      export_version: COMPLIANCE_EXPORT_VERSION,
      generated_at: new Date().toISOString(),
      client_id: clientId,
      client,
      channel_accounts: channelAccounts,
      performance_summary: performanceSummary,
      open_alerts: openAlerts,
      recent_campaign_writes: recentWrites,
      tracking_summary: trackingSummary,
      redaction: {
        tokens_redacted: true,
        pii_redacted: true,
        note: 'Graph tokens and webhook secrets redacted; CAPI payloads omit plaintext PII per SEC-M10.',
      },
    };
  }
}
