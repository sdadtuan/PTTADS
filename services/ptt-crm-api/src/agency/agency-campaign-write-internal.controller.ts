import { Body, Controller, Post, UseGuards } from '@nestjs/common';
import { InternalKeyGuard } from '../auth/internal-key.guard';
import { AgencyService } from './agency.service';

@Controller('api/internal/campaign-writes')
@UseGuards(InternalKeyGuard)
export class AgencyCampaignWriteInternalController {
  constructor(private readonly agency: AgencyService) {}

  @Post('auto-hub-map')
  autoHubMap(
    @Body()
    body: {
      client_id?: string;
      channel?: string;
      external_campaign_id?: string;
      external_campaign_name?: string | null;
      external_account_id?: string | null;
      target_cpl_vnd?: number;
      request_id?: string;
    },
  ) {
    return this.agency.autoMapFromCampaignWrite({
      client_id: String(body.client_id ?? ''),
      channel: String(body.channel ?? 'zalo'),
      external_campaign_id: String(body.external_campaign_id ?? ''),
      external_campaign_name: body.external_campaign_name ?? undefined,
      external_account_id: body.external_account_id ?? undefined,
      target_cpl_vnd: body.target_cpl_vnd,
      request_id: body.request_id,
    });
  }
}
