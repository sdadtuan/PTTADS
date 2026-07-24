import { Body, Controller, Get, Param, Patch, Post, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffMetaTrackingConfigureGuard,
  StaffMetaTrackingViewGuard,
} from './guards/staff-meta-tracking.guard';
import { MetaConversionRulesService } from './meta-conversion-rules.service';
import {
  ConversionRuleMutationResponse,
  ConversionRulesListResponse,
  CreateConversionRuleBody,
  PatchConversionRuleBody,
} from './meta-tracking.types';

@Controller('api/v1/meta/conversion-rules')
export class MetaConversionRulesController {
  constructor(private readonly rules: MetaConversionRulesService) {}

  @Get()
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaTrackingViewGuard)
  listRules(@Query('client_id') clientId?: string): Promise<ConversionRulesListResponse> {
    return this.rules.listRules({ client_id: clientId });
  }

  @Post()
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaTrackingConfigureGuard)
  createRule(@Body() body: CreateConversionRuleBody): Promise<ConversionRuleMutationResponse> {
    return this.rules.createRule(body);
  }

  @Patch(':id')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaTrackingConfigureGuard)
  patchRule(
    @Param('id') id: string,
    @Body() body: PatchConversionRuleBody,
  ): Promise<ConversionRuleMutationResponse> {
    return this.rules.patchRule(id, body);
  }
}
