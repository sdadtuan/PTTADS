import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { CampaignWritesRepository } from '../campaign-writes/campaign-writes.repository';
import { checkCampaignWritePilot } from '../campaign-writes/meta-campaign-write-pilot.util';
import { CreativesRepository } from '../creatives/creatives.repository';
import { LaunchQaPgRepository } from '../service-lifecycle/launch-qa-pg.repository';
import { launchQaProgress } from '../service-lifecycle/lifecycle-launch-gate.util';
import { LaunchQaLifecycleLookupService } from './launch-qa-lifecycle-lookup.service';

const VALID_STATUS_FILTERS = new Set(['all', 'in_progress', 'passed', 'failed', 'blocked', 'timeout']);

@Injectable()
export class LaunchQaHubService {
  constructor(
    private readonly repo: LaunchQaPgRepository,
    private readonly creativesRepo: CreativesRepository,
    private readonly campaignWritesRepo: CampaignWritesRepository,
    private readonly lifecycleLookup: LaunchQaLifecycleLookupService,
  ) {}

  async stats() {
    if (!(await this.repo.pgReady())) {
      throw new ServiceUnavailableException({ error: 'launch_qa_pg_unavailable' });
    }
    const qaStats = await this.repo.countByStatus();
    let pendingCreatives = 0;
    let pendingCampaignWrites = 0;
    if (await this.creativesRepo.pgCreativesReady()) {
      const cStats = await this.creativesRepo.countByStatus();
      pendingCreatives = cStats.pending_client ?? 0;
    }
    if (await this.campaignWritesRepo.tableReady()) {
      const wStats = await this.campaignWritesRepo.countByStatus();
      pendingCampaignWrites = wStats.pending_approval ?? 0;
    }
    return {
      ok: true,
      stats: {
        ...qaStats,
        pending_creatives: pendingCreatives,
        pending_campaign_writes: pendingCampaignWrites,
      },
    };
  }

  async listRuns(status?: string, limit = 100) {
    if (!(await this.repo.pgReady())) {
      throw new ServiceUnavailableException({ error: 'launch_qa_pg_unavailable' });
    }
    const filter = VALID_STATUS_FILTERS.has(String(status ?? 'all').trim())
      ? String(status ?? 'all').trim()
      : 'all';
    const rows = await this.repo.listRuns(filter, Math.min(200, Math.max(1, limit)));
    const lifecycleIndex = this.lifecycleLookup.buildLifecycleIndex();
    const runs = rows.map((row) => {
      const progress = launchQaProgress(row.checklist);
      return {
        id: row.id,
        client_id: row.client_id,
        external_campaign_id: row.external_campaign_id,
        campaign_name: row.campaign_name,
        status: row.status,
        launch_ready: row.launch_ready,
        progress,
        temporal_workflow_id: row.temporal_workflow_id,
        started_by: row.started_by,
        started_at: row.started_at,
        completed_at: row.completed_at,
        lifecycle_id: this.lifecycleLookup.resolveLifecycleId(
          lifecycleIndex,
          row.client_id,
          row.external_campaign_id,
        ),
      };
    });
    return { ok: true, status: filter, count: runs.length, runs };
  }
}
