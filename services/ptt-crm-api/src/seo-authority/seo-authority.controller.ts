import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoAuthorityService } from './seo-authority.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoAuthorityController {
  constructor(private readonly authority: SeoAuthorityService) {}

  @Get('clients/:id/authority/signals')
  async listSignals(
    @Param('id', ParseIntPipe) id: number,
    @Query('signal_type') signalType?: string,
    @Query('status') status?: string,
  ) {
    const [signals, summary] = await Promise.all([
      this.authority.listSignals(id, { signal_type: signalType, status }),
      this.authority.summary(id),
    ]);
    return { ok: true, signals, summary };
  }

  @Post('clients/:id/authority/signals')
  @UseGuards(StaffSeoWriteGuard)
  async addSignal(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const signal = await this.authority.addSignal(id, body);
    return { ok: true, signal };
  }

  @Post('clients/:id/authority/import')
  @UseGuards(StaffSeoWriteGuard)
  async importCsv(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const csvText = String(body.csv_text ?? body.csv ?? '');
    const signalType = String(body.signal_type ?? 'backlink');
    return this.authority.importCsv(id, csvText, signalType);
  }

  @Get('clients/:id/authority/summary')
  async summary(@Param('id', ParseIntPipe) id: number) {
    const summary = await this.authority.summary(id);
    return { ok: true, summary };
  }
}
