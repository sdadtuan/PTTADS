import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  UseGuards,
} from '@nestjs/common';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoExperimentsService } from './seo-experiments.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoExperimentsController {
  constructor(private readonly experiments: SeoExperimentsService) {}

  @Get('experiments/status')
  status() {
    return this.experiments.status();
  }

  @Get('clients/:id/experiments')
  async list(@Param('id', ParseIntPipe) id: number) {
    const items = await this.experiments.listExperiments(id);
    return { ok: true, experiments: items };
  }

  @Get('experiments/:experimentId')
  async detail(@Param('experimentId', ParseIntPipe) experimentId: number) {
    return this.experiments.getExperiment(experimentId);
  }

  @Post('clients/:id/experiments')
  @UseGuards(StaffSeoWriteGuard)
  async create(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    return this.experiments.createExperiment(id, body);
  }

  @Patch('experiments/:experimentId/status')
  @UseGuards(StaffSeoWriteGuard)
  async updateStatus(
    @Param('experimentId', ParseIntPipe) experimentId: number,
    @Body() body: Record<string, unknown>,
  ) {
    return this.experiments.updateStatus(experimentId, String(body.status ?? ''));
  }

  @Post('experiments/:experimentId/observations')
  @UseGuards(StaffSeoWriteGuard)
  async addObservation(
    @Param('experimentId', ParseIntPipe) experimentId: number,
    @Body() body: Record<string, unknown>,
  ) {
    return this.experiments.addObservation(experimentId, body);
  }
}
