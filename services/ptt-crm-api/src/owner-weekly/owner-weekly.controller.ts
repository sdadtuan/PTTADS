import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffOwnerWeeklyConfigureGuard,
  StaffOwnerWeeklyExportGuard,
  StaffOwnerWeeklyViewGuard,
} from './guards/staff-owner-weekly.guard';
import { OwnerWeeklyService } from './owner-weekly.service';

@Controller('api/crm/owner-weekly')
@UseGuards(StaffOrInternalKeyGuard)
export class OwnerWeeklyController {
  constructor(private readonly ownerWeekly: OwnerWeeklyService) {}

  @Get()
  @UseGuards(StaffOwnerWeeklyViewGuard)
  dashboard(
    @Query('year') year?: string,
    @Query('week') week?: string,
    @Query('trend_weeks') trendWeeks?: string,
    @Query('week_end') weekEnd?: string,
  ) {
    return this.ownerWeekly.dashboard({ year, week, trend_weeks: trendWeeks, week_end: weekEnd });
  }

  @Get('config')
  @UseGuards(StaffOwnerWeeklyViewGuard)
  configGet() {
    return this.ownerWeekly.configGet();
  }

  @Patch('config')
  @UseGuards(StaffOwnerWeeklyConfigureGuard)
  configPatch(@Body() body: Record<string, unknown>) {
    return this.ownerWeekly.configPatch(body);
  }

  @Get('cash-snapshots')
  @UseGuards(StaffOwnerWeeklyViewGuard)
  listCashSnapshots(@Query('limit') limit?: string) {
    return this.ownerWeekly.listCashSnapshots(limit);
  }

  @Post('cash-snapshots')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOwnerWeeklyConfigureGuard)
  upsertCashSnapshot(@Body() body: Record<string, unknown>) {
    return this.ownerWeekly.upsertCashSnapshot(body);
  }

  @Delete('cash-snapshots')
  @UseGuards(StaffOwnerWeeklyConfigureGuard)
  deleteCashSnapshot(
    @Query('snapshot_on') snapshotOn?: string,
    @Body() body?: Record<string, unknown>,
  ) {
    return this.ownerWeekly.deleteCashSnapshot({ snapshot_on: snapshotOn }, body);
  }

  @Get('export')
  @UseGuards(StaffOwnerWeeklyExportGuard)
  export(
    @Query('year') year?: string,
    @Query('week') week?: string,
    @Query('week_end') weekEnd?: string,
    @Query('format') format?: string,
  ) {
    void format;
    return this.ownerWeekly.export({ year, week, week_end: weekEnd });
  }

  @Post('alert-cron')
  @HttpCode(HttpStatus.OK)
  alertCron(@Body() body: Record<string, unknown>, @Query() query: Record<string, string>) {
    return this.ownerWeekly.alertCron(body, query);
  }

  @Post('inbox/sync')
  @HttpCode(HttpStatus.OK)
  inboxSync(@Body() body: Record<string, unknown>, @Query() query: Record<string, string>) {
    return this.ownerWeekly.inboxSync(body, query);
  }

  @Get('inbox/summary')
  @UseGuards(StaffOwnerWeeklyViewGuard)
  inboxSummary() {
    return this.ownerWeekly.inboxSummary();
  }
}
