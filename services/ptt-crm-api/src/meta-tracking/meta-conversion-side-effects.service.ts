import { Injectable, Logger } from '@nestjs/common';
import { EnqueuedJob, JobQueueRepository } from '../webhooks/job-queue.repository';

@Injectable()
export class MetaConversionSideEffectsService {
  private readonly logger = new Logger(MetaConversionSideEffectsService.name);

  constructor(private readonly jobQueue: JobQueueRepository) {}

  isConversionHookEnabled(): boolean {
    const tracking = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
    );
    const capi =
      ['1', 'true', 'yes', 'on'].includes(
        (process.env.PTT_CAPI_ENABLED ?? '0').trim().toLowerCase(),
      ) ||
      ['1', 'true', 'yes', 'on'].includes(
        (process.env.PTT_CAPI_STUB ?? '0').trim().toLowerCase(),
      );
    return tracking && capi;
  }

  async enqueueConversionEval(input: {
    leadId: number;
    clientId: string | null;
    oldStatus: string | null;
    newStatus: string;
  }): Promise<EnqueuedJob | null> {
    if (!this.isConversionHookEnabled()) {
      return null;
    }
    const clientId = input.clientId?.trim();
    if (!clientId) {
      return null;
    }
    const oldNorm = (input.oldStatus ?? '').trim().toLowerCase();
    const newNorm = input.newStatus.trim().toLowerCase();
    if (!newNorm || oldNorm === newNorm) {
      return null;
    }

    try {
      const job = await this.jobQueue.enqueueMetaConversionEval({
        payload: {
          lead_id: input.leadId,
          client_id: clientId,
          old_status: oldNorm || null,
          new_status: newNorm,
          mode: 'dispatch',
        },
        idempotencyKey: `meta_conversion_eval:${clientId}:${input.leadId}:${oldNorm}->${newNorm}`,
        clientId,
      });
      if (job) {
        this.logger.debug(
          `meta_conversion_eval enqueued lead=${input.leadId} ${oldNorm}->${newNorm}`,
        );
      }
      return job;
    } catch (err) {
      this.logger.warn(`meta_conversion_eval enqueue skipped lead=${input.leadId}: ${String(err)}`);
      return null;
    }
  }
}
