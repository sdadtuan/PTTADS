import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffMetaIntelligenceConfigureGuard } from './guards/staff-meta-intelligence-configure.guard';
import { StaffMetaIntelligenceViewGuard } from './guards/staff-meta-intelligence.guard';
import { MetaIntelligenceController } from './meta-intelligence.controller';
import { MetaIntelligenceRepository } from './meta-intelligence.repository';
import { MetaIntelligenceService } from './meta-intelligence.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [MetaIntelligenceController],
  providers: [
    MetaIntelligenceRepository,
    MetaIntelligenceService,
    StaffMetaIntelligenceViewGuard,
    StaffMetaIntelligenceConfigureGuard,
  ],
  exports: [MetaIntelligenceService, MetaIntelligenceRepository],
})
export class MetaIntelligenceModule {}
