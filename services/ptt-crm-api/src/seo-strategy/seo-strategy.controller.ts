import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  UseGuards,
} from '@nestjs/common';
import {
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
  StaffSeoWriteGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoStrategyService } from './seo-strategy.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoStrategyController {
  constructor(private readonly strategy: SeoStrategyService) {}

  @Get('clients/:id/strategy/okr')
  async okr(@Param('id', ParseIntPipe) id: number) {
    const tree = await this.strategy.okrTree(id);
    return { ok: true, ...tree };
  }

  @Post('clients/:id/strategy/goals')
  @UseGuards(StaffSeoWriteGuard)
  async createGoal(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const goal = await this.strategy.createGoal(id, body);
    return { ok: true, goal };
  }

  @Post('clients/:id/strategy/kpis')
  @UseGuards(StaffSeoWriteGuard)
  async createKpi(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const kpi = await this.strategy.createKpi(id, body);
    return { ok: true, kpi };
  }

  @Post('clients/:id/strategy/kpis/refresh')
  @UseGuards(StaffSeoSettingsGuard)
  async refresh(@Param('id', ParseIntPipe) id: number) {
    return this.strategy.refreshKpis(id);
  }

  @Post('clients/:id/strategy/initiatives/:iid/link-goal')
  @UseGuards(StaffSeoWriteGuard)
  async linkGoal(
    @Param('id', ParseIntPipe) id: number,
    @Param('iid', ParseIntPipe) initiativeId: number,
    @Body() body: { goal_id: number | null },
  ) {
    return this.strategy.linkInitiative(id, initiativeId, body.goal_id ?? null);
  }
}
