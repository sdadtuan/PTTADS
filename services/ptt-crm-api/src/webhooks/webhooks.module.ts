import { Module } from '@nestjs/common';
import { WebhooksEnabledGuard } from './guards/webhooks-enabled.guard';
import { JobQueueRepository } from './job-queue.repository';
import { MetaWebhookRepository } from './meta-webhook.repository';
import { WebhooksController } from './webhooks.controller';
import { WebhooksService } from './webhooks.service';

@Module({
  controllers: [WebhooksController],
  providers: [WebhooksService, JobQueueRepository, MetaWebhookRepository, WebhooksEnabledGuard],
  exports: [WebhooksService, JobQueueRepository, MetaWebhookRepository],
})
export class WebhooksModule {}
