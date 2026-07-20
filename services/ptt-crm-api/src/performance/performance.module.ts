import { Module } from '@nestjs/common';
import { PortalModule } from '../portal/portal.module';
import { PerformanceController } from './performance.controller';
import { PerformanceRepository } from './performance.repository';
import { PerformanceService } from './performance.service';

@Module({
  imports: [PortalModule],
  controllers: [PerformanceController],
  providers: [PerformanceRepository, PerformanceService],
  exports: [PerformanceService],
})
export class PerformanceModule {}
