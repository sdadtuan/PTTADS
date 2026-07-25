import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import {
  StaffSeoSettingsGuard,
  StaffSeoTechnicalGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoCmsService } from './seo-cms.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoCmsController {
  constructor(private readonly cms: SeoCmsService) {}

  @Get('clients/:id/cms-target')
  target(@Param('id', ParseIntPipe) id: number) {
    return this.cms.getTarget(id);
  }

  @Put('clients/:id/cms-target')
  @UseGuards(StaffSeoSettingsGuard)
  upsertTarget(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    return this.cms.upsertTarget(id, body);
  }

  @Get('clients/:id/cms-jobs')
  jobs(@Param('id', ParseIntPipe) id: number, @Query('limit') limit?: string) {
    const lim = limit ? Number.parseInt(limit, 10) : 50;
    return this.cms.listJobs(id, lim);
  }

  @Post('clients/:id/cms/test')
  @UseGuards(StaffSeoSettingsGuard)
  test(@Param('id', ParseIntPipe) id: number) {
    return this.cms.testWebhook(id);
  }

  @Post('clients/:id/cms/publish/:contentId')
  @UseGuards(StaffSeoTechnicalGuard)
  publish(
    @Param('id', ParseIntPipe) id: number,
    @Param('contentId', ParseIntPipe) contentId: number,
    @Query('dry_run') dryRun?: string,
  ) {
    void id;
    return this.cms.queuePublish(contentId, dryRun === '1' || dryRun === 'true');
  }
}
