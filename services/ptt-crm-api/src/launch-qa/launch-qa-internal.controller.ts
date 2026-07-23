import { Body, Controller, Post, UseGuards } from '@nestjs/common';
import { InternalKeyGuard } from '../auth/internal-key.guard';
import { LaunchQaCampaignWriteBridgeService } from './launch-qa-campaign-write-bridge.service';

@Controller('api/internal/launch-qa')
@UseGuards(InternalKeyGuard)
export class LaunchQaInternalController {
  constructor(private readonly budgetBridge: LaunchQaCampaignWriteBridgeService) {}

  @Post('sync-budget-confirmed')
  syncBudgetConfirmed(
    @Body()
    body: {
      client_id?: string;
      external_campaign_id?: string;
      executed_by?: string;
      request_id?: string;
    },
  ) {
    return this.budgetBridge.onBudgetExecuted({
      clientId: String(body.client_id ?? ''),
      externalCampaignId: String(body.external_campaign_id ?? ''),
      executedBy: body.executed_by,
      requestId: body.request_id,
    });
  }
}
