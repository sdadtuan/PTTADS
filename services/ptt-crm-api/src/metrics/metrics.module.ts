import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { MetricsController } from './metrics.controller';
import { MetricsRepository } from './metrics.repository';
import { MetricsService } from './metrics.service';
import { StaffMetricsViewGuard } from './guards/staff-metrics.guard';

@Module({
  imports: [StaffAuthModule],
  controllers: [MetricsController],
  providers: [MetricsRepository, MetricsService, StaffMetricsViewGuard],
  exports: [MetricsService],
})
export class MetricsModule {}
