import { Injectable } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { catalogTs } from '../catalog/catalog-slug.util';
import { SopSqliteRepository } from './sop-sqlite.repository';
import { shouldReuseLifecycleSopRun } from './sop-auto-start.util';

const LAUNCH_TEMPLATE_CODE = 'MKT-LAUNCH-14D';

export interface SopAutoStartResult {
  started: boolean;
  run_id?: number;
  idempotent?: boolean;
  reason?: string;
}

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
  }): SopAutoStartResult {
    if (!this.config.sopAutoStartOnLaunch) {
      return { started: false, reason: 'PTT_SOP_AUTO_START_ON_LAUNCH disabled' };
    }

    const existingRunId = this.getLifecycleSopRunId(input.lifecycleId);
    if (shouldReuseLifecycleSopRun(existingRunId, !!this.sop.getRunById(existingRunId!))) {
      return {
        started: true,
        run_id: existingRunId!,
        idempotent: true,
        reason: 'lifecycle_once',
      };
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
    const runId = Number((run as { id?: number }).id ?? 0);
    if (!runId) {
      return { started: false, reason: 'Failed to create SOP run' };
    }
    this.setLifecycleSopRunId(input.lifecycleId, runId);
    return { started: true, run_id: runId };
  }

  private getLifecycleSopRunId(lifecycleId: number): number | null {
    try {
      const db = (this.sop as unknown as { database: import('node:sqlite').DatabaseSync }).database;
      const row = db
        .prepare(`SELECT sop_run_id FROM crm_service_lifecycle WHERE id = ? LIMIT 1`)
        .get(lifecycleId) as { sop_run_id: number | null } | undefined;
      const rid = row?.sop_run_id != null ? Number(row.sop_run_id) : 0;
      return rid > 0 ? rid : null;
    } catch {
      return null;
    }
  }

  private setLifecycleSopRunId(lifecycleId: number, runId: number): void {
    const db = (this.sop as unknown as { database: import('node:sqlite').DatabaseSync }).database;
    db.prepare(
      `UPDATE crm_service_lifecycle SET sop_run_id = ?, updated_at = ? WHERE id = ?`,
    ).run(runId, catalogTs(), lifecycleId);
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
