import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { MetaAlertsController } from './meta-alerts.controller';
import { MetaAlertsRepository } from './meta-alerts.repository';
import { MetaAlertsService } from './meta-alerts.service';
import { StaffMetaAlertsAckGuard, StaffMetaAlertsViewGuard } from './guards/staff-meta-alerts.guard';

@Module({
  imports: [StaffAuthModule],
  controllers: [MetaAlertsController],
  providers: [
    MetaAlertsRepository,
    MetaAlertsService,
    StaffMetaAlertsViewGuard,
    StaffMetaAlertsAckGuard,
  ],
  exports: [MetaAlertsService],
})
export class MetaAlertsModule {}
