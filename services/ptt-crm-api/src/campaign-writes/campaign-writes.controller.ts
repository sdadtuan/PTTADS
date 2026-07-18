import { Body, Controller, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
import { InternalKeyGuard } from '../auth/internal-key.guard';
import { CampaignWritesService } from './campaign-writes.service';
import { ApproveCampaignWriteBody, SubmitCampaignWriteBody } from './campaign-writes.types';

@Controller('api/v1/campaign-writes')
@UseGuards(InternalKeyGuard)
export class CampaignWritesController {
  constructor(private readonly service: CampaignWritesService) {}

  @Post()
  submit(@Body() body: SubmitCampaignWriteBody) {
    return this.service.submit(body);
  }

  @Get('pending')
  listPending(@Query('client_id') clientId?: string) {
    return this.service.listPending(clientId);
  }

  @Post(':id/approve')
  approve(@Param('id') id: string, @Body() body: ApproveCampaignWriteBody) {
    return this.service.approve(id, body ?? {});
  }

  @Post(':id/reject')
  reject(@Param('id') id: string, @Body() body: ApproveCampaignWriteBody) {
    return this.service.reject(id, body ?? {});
  }
}
