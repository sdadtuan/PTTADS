import { Injectable } from '@nestjs/common';
import { cmsAutoPublishEnabled } from './seo-cms.constants';
import { SeoCmsRepository } from './seo-cms.repository';
import { SeoCmsPublishResult, SeoCmsTargetRow } from './seo-cms.types';

@Injectable()
export class SeoCmsService {
  constructor(private readonly repo: SeoCmsRepository) {}

  getTarget(customerId: number) {
    return this.repo.getTarget(customerId).then((target) => ({ ok: true, target }));
  }

  upsertTarget(customerId: number, body: Record<string, unknown>): Promise<{ ok: boolean; target: SeoCmsTargetRow }> {
    return this.repo.upsertTarget(customerId, body).then((target) => ({ ok: true, target }));
  }

  listJobs(customerId: number, limit?: number) {
    return this.repo.listJobs(customerId, limit ?? 50).then((jobs) => ({ ok: true, jobs }));
  }

  queuePublish(contentId: number, dryRun = false): Promise<{ ok: boolean } & SeoCmsPublishResult> {
    return this.repo.queuePublish(contentId, dryRun).then((result) => ({ ok: true, ...result }));
  }

  testWebhook(customerId: number) {
    return this.repo.testWebhook(customerId);
  }

  async maybeAutoPublish(contentId: number): Promise<SeoCmsPublishResult | null> {
    if (!cmsAutoPublishEnabled()) return null;
    const content = await this.repo.getContentPublishState(contentId);
    if (!content || content.workflow_status !== 'published') return null;
    const target = await this.repo.getTarget(content.customer_id);
    if (!target?.active) return null;
    try {
      return await this.repo.queuePublish(contentId);
    } catch {
      return null;
    }
  }

  receivePilotWebhook(body: Record<string, unknown>) {
    return {
      ok: true,
      received: true,
      event: String(body.event ?? 'unknown'),
      title: body.title ?? null,
      customer_id: body.customer_id ?? null,
      timestamp: new Date().toISOString(),
    };
  }
}
