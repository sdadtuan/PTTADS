import { Injectable } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { catalogTs } from '../catalog/catalog-slug.util';
import { SopSqliteRepository } from './sop-sqlite.repository';

const LAUNCH_TEMPLATE_CODE = 'MKT-LAUNCH-14D';

@Injectable()
export class SopAutoStartService {
  constructor(
    private readonly sop: SopSqliteRepository,
    private readonly config: AppConfigService,
  ) {}

  maybeStartOnLifecyclePromote(input: {
    lifecycleId: number;
    contractId?: number | null;
    customerName?: string;
    serviceSlug?: string;
  }): { started: boolean; run_id?: number; reason?: string } {
    if (!this.config.sopAutoStartOnLaunch) {
      return { started: false, reason: 'PTT_SOP_AUTO_START_ON_LAUNCH disabled' };
    }
    const template = this.sop.getTemplateByCode(LAUNCH_TEMPLATE_CODE);
    if (!template) {
      return { started: false, reason: `Template ${LAUNCH_TEMPLATE_CODE} not found` };
    }
    const campaignId = input.contractId ? this.findCampaignForContract(input.contractId) : null;
    const name = [
      'Launch SOP',
      input.customerName?.trim() || `Lifecycle #${input.lifecycleId}`,
      input.serviceSlug ? `(${input.serviceSlug})` : '',
    ]
      .filter(Boolean)
      .join(' — ')
      .slice(0, 200);
    const run = this.sop.createRun(
      {
        name,
        template_id: template.id,
        campaign_id: campaignId ?? undefined,
        start_date: catalogTs().slice(0, 10),
        generate_tasks: true,
      },
      true,
    );
    return { started: true, run_id: Number((run as { id?: number }).id ?? 0) || undefined };
  }

  private findCampaignForContract(contractId: number): number | null {
    try {
      const db = (this.sop as unknown as { database: import('node:sqlite').DatabaseSync }).database;
      const row = db
        .prepare(`SELECT campaign_id FROM crm_contracts WHERE id = ? LIMIT 1`)
        .get(contractId) as { campaign_id: number | null } | undefined;
      const cid = row?.campaign_id != null ? Number(row.campaign_id) : 0;
      return cid > 0 ? cid : null;
    } catch {
      return null;
    }
  }
}
