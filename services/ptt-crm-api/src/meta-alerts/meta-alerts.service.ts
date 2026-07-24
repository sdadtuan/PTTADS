import { Injectable, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { MetaAlertsRepository } from './meta-alerts.repository';
import { MetaAlertAckResponse, MetaAlertsListResponse } from './meta-alerts.types';

@Injectable()
export class MetaAlertsService {
  constructor(private readonly repo: MetaAlertsRepository) {}

  private async ensureReady(): Promise<void> {
    if (!(await this.repo.pgMetaAlertsReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_alerts_not_ready' });
    }
  }

  private isAlertsEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_ALERTS_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  async list(query: {
    client_id?: string;
    include_ack?: string;
    limit?: string;
  }): Promise<MetaAlertsListResponse> {
    await this.ensureReady();
    if (!this.isAlertsEnabled()) {
      return { ok: true, alerts: [], count: 0, open_count: 0 };
    }
    const openOnly = query.include_ack !== '1' && query.include_ack !== 'true';
    const limit = query.limit ? Number(query.limit) : 100;
    const alerts = await this.repo.listAlerts({
      clientId: query.client_id?.trim() || undefined,
      openOnly,
      limit: Number.isFinite(limit) ? limit : 100,
    });
    const openCount = alerts.filter((a) => !a.acknowledged_at).length;
    return { ok: true, alerts, count: alerts.length, open_count: openCount };
  }

  async acknowledge(alertId: string): Promise<MetaAlertAckResponse> {
    await this.ensureReady();
    if (!this.isAlertsEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_alerts_disabled' });
    }
    const alert = await this.repo.acknowledgeAlert(alertId.trim());
    if (!alert) {
      throw new NotFoundException({ error: 'alert_not_found' });
    }
    return { ok: true, alert };
  }
}
