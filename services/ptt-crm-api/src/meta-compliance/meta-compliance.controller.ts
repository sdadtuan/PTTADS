import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffMetaComplianceExportGuard } from './guards/staff-meta-compliance.guard';
import { MetaComplianceService } from './meta-compliance.service';
import { MetaComplianceExportResponse } from './meta-compliance.types';

@Controller('api/v1/meta/compliance')
export class MetaComplianceController {
  constructor(private readonly compliance: MetaComplianceService) {}

  @Get('export')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaComplianceExportGuard)
  export(
    @Query('client_id') clientId: string,
    @Query('days') days?: string,
  ): Promise<MetaComplianceExportResponse> {
    return this.compliance.exportBundle(String(clientId ?? '').trim(), days);
  }
}
