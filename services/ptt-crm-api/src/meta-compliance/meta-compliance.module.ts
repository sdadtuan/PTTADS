import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { MetaComplianceController } from './meta-compliance.controller';
import { MetaComplianceRepository } from './meta-compliance.repository';
import { MetaComplianceService } from './meta-compliance.service';
import { StaffMetaComplianceExportGuard } from './guards/staff-meta-compliance.guard';

@Module({
  imports: [StaffAuthModule],
  controllers: [MetaComplianceController],
  providers: [
    MetaComplianceRepository,
    MetaComplianceService,
    StaffMetaComplianceExportGuard,
  ],
  exports: [MetaComplianceService],
})
export class MetaComplianceModule {}
