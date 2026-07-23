import { BadRequestException, ForbiddenException, Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { TemporalClientService } from '../temporal/temporal-client.service';

export interface StartOnboardingBody {
  client_id: string;
  started_by?: string;
}

export interface StartLaunchQaBody {
  client_id: string;
  external_campaign_id: string;
  campaign_name?: string;
  started_by?: string;
}

@Injectable()
export class WorkflowsService implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(
    private readonly config: AppConfigService,
    private readonly temporal: TemporalClientService,
  ) {}

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  async startOnboarding(body: StartOnboardingBody) {
    const clientId = body.client_id?.trim();
    if (!clientId) {
      throw new BadRequestException({ error: 'client_id required' });
    }
    await this.assertClientNotArchived(clientId);
    if (!(await this.clientExists(clientId))) {
      throw new NotFoundException({ error: 'client_not_found' });
    }
    const startedBy = body.started_by?.trim() || 'am@pttads.vn';
    const workflowId = this.temporal.onboardingWorkflowId(clientId);
    const wf = await this.temporal.startWorkflow('ClientOnboardingWorkflow', workflowId, [
      { client_id: clientId, started_by: startedBy },
    ]);
    return {
      ok: true,
      client_id: clientId,
      workflow_id: wf.workflowId,
      workflow_started: wf.started,
      temporal_run_id: wf.runId,
      temporal_signal: wf.started ? 'sent' : this.temporal.isEnabled() ? 'skipped' : 'stub',
    };
  }

  async nudgeOnboarding(clientId: string) {
    await this.assertClientNotArchived(clientId.trim());
    const wfId = this.temporal.onboardingWorkflowId(clientId.trim());
    const signal = await this.temporal.signalWorkflow(wfId, 'checklist_updated', {});
    return { ok: true, workflow_id: wfId, temporal_signal: signal };
  }

  async startLaunchQa(body: StartLaunchQaBody) {
    const clientId = body.client_id?.trim();
    const campaignId = body.external_campaign_id?.trim();
    if (!clientId || !campaignId) {
      throw new BadRequestException({ error: 'client_id and external_campaign_id required' });
    }
    if (!(await this.clientExists(clientId))) {
      throw new NotFoundException({ error: 'client_not_found' });
    }
    const startedBy = body.started_by?.trim() || 'am@pttads.vn';
    const checklist = {
      pixel_verified: { label: 'Pixel / dataset verified', completed: false },
      naming_convention: { label: 'Naming convention OK', completed: false },
      budget_confirmed: { label: 'Budget confirmed with client', completed: false },
      creative_approved: { label: 'Creative client-approved', completed: false },
      utm_tracking: { label: 'UTM tracking template', completed: false },
      qa_signoff: { label: 'PM / QA sign-off', completed: false },
    };
    const insert = await this.db.query(
      `INSERT INTO launch_qa_runs (
         client_id, external_campaign_id, campaign_name, checklist, started_by
       ) VALUES ($1::uuid, $2, $3, $4::jsonb, $5)
       RETURNING id::text`,
      [
        clientId,
        campaignId,
        body.campaign_name?.trim() || null,
        JSON.stringify(checklist),
        startedBy,
      ],
    );
    const runId = String(insert.rows[0]?.id ?? '');
    const workflowId = this.temporal.launchQaWorkflowId(runId);
    const wf = await this.temporal.startWorkflow('LaunchQAWorkflow', workflowId, [
      {
        run_id: runId,
        client_id: clientId,
        external_campaign_id: campaignId,
        started_by: startedBy,
        campaign_name: body.campaign_name?.trim() || null,
      },
    ]);
    await this.db.query(
      `UPDATE launch_qa_runs SET temporal_workflow_id = $2, temporal_run_id = $3, updated_at = NOW()
       WHERE id = $1::uuid`,
      [runId, wf.workflowId, wf.runId],
    );
    return {
      ok: true,
      run_id: runId,
      client_id: clientId,
      workflow_id: wf.workflowId,
      workflow_started: wf.started,
      temporal_run_id: wf.runId,
    };
  }

  async nudgeLaunchQa(runId: string) {
    const wfId = this.temporal.launchQaWorkflowId(runId.trim());
    const signal = await this.temporal.signalWorkflow(wfId, 'checklist_updated', {});
    return { ok: true, run_id: runId, workflow_id: wfId, temporal_signal: signal };
  }

  async onboardingStatus(clientId: string) {
    const wfId = this.temporal.onboardingWorkflowId(clientId.trim());
    const desc = await this.temporal.describeWorkflow(wfId);
    return { ok: true, client_id: clientId, ...desc };
  }

  async launchQaStatus(runId: string) {
    const wfId = this.temporal.launchQaWorkflowId(runId.trim());
    const desc = await this.temporal.describeWorkflow(wfId);
    return { ok: true, ...desc, run_id: runId };
  }

  async creativeStatus(creativeId: string) {
    const wfId = this.temporal.creativeWorkflowId(creativeId.trim());
    const desc = await this.temporal.describeWorkflow(wfId);
    return { ok: true, creative_id: creativeId, ...desc };
  }

  private async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [
      clientId,
    ]);
    return (result.rowCount ?? 0) > 0;
  }

  private async assertClientNotArchived(clientId: string): Promise<void> {
    try {
      const result = await this.db.query(
        `SELECT tenant_locked FROM clients WHERE id = $1::uuid LIMIT 1`,
        [clientId],
      );
      const row = result.rows[0] as { tenant_locked?: boolean } | undefined;
      if (row && Boolean(row.tenant_locked)) {
        throw new ForbiddenException({ error: 'tenant_archived', client_id: clientId });
      }
    } catch (err) {
      if (err instanceof ForbiddenException) {
        throw err;
      }
      // tenant_locked column may be absent before B7.1 DDL — ignore lookup errors
    }
  }
}
