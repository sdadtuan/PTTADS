import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffMarketingPlansViewGuard,
  StaffMarketingPlansWriteGuard,
} from './guards/staff-marketing-plans.guard';
import { MarketingPlansController } from './marketing-plans.controller';
import { MarketingPlansSqliteRepository } from './marketing-plans-sqlite.repository';
import { MarketingPlansService } from './marketing-plans.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [MarketingPlansController],
  providers: [
    MarketingPlansService,
    MarketingPlansSqliteRepository,
    StaffMarketingPlansViewGuard,
    StaffMarketingPlansWriteGuard,
  ],
  exports: [MarketingPlansService],
})
export class MarketingPlansModule {}
